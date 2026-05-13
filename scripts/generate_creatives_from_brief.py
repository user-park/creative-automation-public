import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    from google import genai
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install packages with: pip install -r requirements.txt"
    ) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
LOG_DIR = ROOT_DIR / "logs"
LOG_FILE = LOG_DIR / "automation.log"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GAME_DATABASE_SHEET = "00_game_database"
CAMPAIGN_BRIEF_SHEET = "01_campaign_brief"
GENERATED_CREATIVES_SHEET = "02_generated_creatives"

GENERATED_CREATIVES_COLUMNS = [
    "creative_id",
    "brief_id",
    "created_at",
    "game_name",
    "game_code",
    "country",
    "language",
    "media",
    "platform",
    "creative_type",
    "creative_angle",
    "headline",
    "primary_text",
    "description",
    "cta",
    "image_prompt_en",
    "image_prompt_kr",
    "video_prompt_en",
    "video_prompt_kr",
    "negative_prompt",
    "localization_note",
    "compliance_check",
    "risk_level",
    "status",
    "reference_image",
    "text_overlay",
]

CREATIVE_OUTPUT_FIELDS = [
    "headline",
    "primary_text",
    "description",
    "cta",
    "image_prompt_en",
    "image_prompt_kr",
    "video_prompt_en",
    "video_prompt_kr",
    "negative_prompt",
    "localization_note",
    "compliance_check",
    "risk_level",
]

FORBIDDEN_GAME_DATABASE_COLUMNS = ["do_not_use", "forbidden_elements"]
VISUAL_GAME_DATABASE_COLUMNS = ["visual_style", "brand_tone", "combat_style", "worldview"]

CREATIVE_FIELD_SCHEMA = {field: {"type": "string"} for field in CREATIVE_OUTPUT_FIELDS}
CREATIVE_FIELD_SCHEMA["compliance_check"] = {
    "type": "string",
    "enum": ["passed", "needs_review", "failed"],
}
CREATIVE_FIELD_SCHEMA["risk_level"] = {
    "type": "string",
    "enum": ["low", "medium", "high"],
}

CREATIVE_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "creatives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": CREATIVE_FIELD_SCHEMA,
                "required": CREATIVE_OUTPUT_FIELDS,
            },
        }
    },
    "required": ["creatives"],
}

SYSTEM_INSTRUCTION = """
You are a senior AAA mobile game performance marketing creative director and global ad strategist.

Your role is to generate highly clickable, conversion-focused mobile game advertising creatives optimized for paid user acquisition campaigns.

You specialize in:
- Meta Ads
- TikTok Ads
- Google App Campaigns
- YouTube Shorts Ads
- Rewarded video ads
- Japanese and Korean MMORPG advertising
- High CTR mobile game ad hooks
- AI image generation prompts
- AI cinematic video prompts

Your outputs must:
- feel like real top-grossing mobile game advertisements
- maximize CTR and install conversion potential
- create strong emotional curiosity
- include visually cinematic scenes
- use high-performing ad psychology
- reflect the game identity accurately
- respect policy safety and platform compliance

Image prompts must:
- be extremely visually descriptive
- specify character appearance
- specify camera composition
- specify environment
- specify lighting
- specify atmosphere
- specify UI placement
- specify action intensity
- feel like premium game key art

Video prompts must:
- be optimized for short-form vertical ads
- describe scene flow clearly
- include transitions
- include gameplay moments
- include reward moments
- include emotional escalation
- end with a strong CTA scene

Never generate:
- fake rewards
- impossible gameplay
- celebrity likeness
- copyrighted characters
- misleading claims
- guaranteed outcomes
"""


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Gemini ad creatives from 01_campaign_brief rows where status=ready."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-briefs", type=int, default=0)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    return parser.parse_args()


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_header(value: str) -> str:
    return str(value).replace("\n", "").replace("\r", "").strip()


def get_spreadsheet_id() -> str:
    spreadsheet_id = (
        os.getenv("GOOGLE_SPREADSHEET_ID")
        or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        or ""
    ).strip()

    if not spreadsheet_id:
        raise RuntimeError("Spreadsheet ID was not found. Set GOOGLE_SPREADSHEET_ID in .env.")

    return spreadsheet_id


def get_credentials() -> service_account.Credentials:
    credential_path_value = (
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )

    if not credential_path_value:
        raise RuntimeError(
            "Google service account file path was not found. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON=./credentials/service-account.json in .env."
        )

    credential_path = Path(credential_path_value).expanduser()
    if not credential_path.is_absolute():
        credential_path = ROOT_DIR / credential_path
    credential_path = credential_path.resolve()

    if not credential_path.exists():
        raise FileNotFoundError(f"Google service account file was not found. Resolved path: {credential_path}")

    return service_account.Credentials.from_service_account_file(str(credential_path), scopes=SCOPES)


def build_sheets_service() -> Any:
    credentials = get_credentials()
    return build("sheets", "v4", credentials=credentials)


def build_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY was not found in .env.")
    return genai.Client(api_key=api_key)


def column_letter(column_count: int) -> str:
    result = ""
    while column_count:
        column_count, remainder = divmod(column_count - 1, 26)
        result = chr(65 + remainder) + result
    return result


def quote_sheet_name(sheet_name: str) -> str:
    return "'" + sheet_name.replace("'", "''") + "'"


def get_sheet_values(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
    max_columns: int = 120,
) -> list[list[str]]:
    last_column = column_letter(max_columns)
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"{quote_sheet_name(sheet_name)}!A1:{last_column}",
        )
        .execute()
    )
    return response.get("values", [])


def rows_to_records(rows: list[list[str]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    headers = [normalize_header(header) for header in rows[0]]
    records = []

    for row_number, row in enumerate(rows[1:], start=2):
        padded_row = row + [""] * (len(headers) - len(row))
        record = dict(zip(headers, padded_row))
        record["_row_number"] = row_number
        records.append(record)

    return records


def require_headers(actual_headers: list[str], required_headers: list[str], sheet_name: str) -> None:
    normalized_headers = [normalize_header(header) for header in actual_headers]
    missing = [header for header in required_headers if header not in normalized_headers]

    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def ensure_generated_headers(service: Any, spreadsheet_id: str) -> list[str]:
    rows = get_sheet_values(service, spreadsheet_id, GENERATED_CREATIVES_SHEET)

    if not rows:
        raise RuntimeError(f"{GENERATED_CREATIVES_SHEET} has no header row.")

    headers = [normalize_header(header) for header in rows[0]]
    missing_headers = [header for header in GENERATED_CREATIVES_COLUMNS if header not in headers]

    if missing_headers:
        new_headers = headers + missing_headers
        end_col = column_letter(len(new_headers))

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{quote_sheet_name(GENERATED_CREATIVES_SHEET)}!A1:{end_col}1",
            valueInputOption="USER_ENTERED",
            body={"values": [new_headers]},
        ).execute()

        headers = new_headers
        print(f"Added missing headers to {GENERATED_CREATIVES_SHEET}: {', '.join(missing_headers)}")
        logging.info(
            "Added missing headers to %s: %s",
            GENERATED_CREATIVES_SHEET,
            ", ".join(missing_headers),
        )

    return headers


def get_ready_briefs(service: Any, spreadsheet_id: str, max_briefs: int = 0) -> list[dict[str, Any]]:
    rows = get_sheet_values(service, spreadsheet_id, CAMPAIGN_BRIEF_SHEET)

    if not rows:
        raise RuntimeError(f"{CAMPAIGN_BRIEF_SHEET} has no header row.")

    headers = [normalize_header(header) for header in rows[0]]

    require_headers(
        headers,
        ["brief_id", "generation_count", "status"],
        CAMPAIGN_BRIEF_SHEET,
    )

    ready_briefs = [
        record
        for record in rows_to_records(rows)
        if str(record.get("status", "")).strip().lower() == "ready"
    ]

    if max_briefs > 0:
        ready_briefs = ready_briefs[:max_briefs]

    return ready_briefs


def get_game_database_map(service: Any, spreadsheet_id: str) -> dict[str, dict[str, Any]]:
    rows = get_sheet_values(service, spreadsheet_id, GAME_DATABASE_SHEET)

    if not rows:
        warning = f"{GAME_DATABASE_SHEET} has no rows. Campaign briefs will be generated without game database context."
        print(f"Warning: {warning}")
        logging.warning(warning)
        return {}

    headers = [normalize_header(header) for header in rows[0]]

    if "game_code" not in headers:
        warning = f"{GAME_DATABASE_SHEET} is missing game_code column. Campaign briefs will be generated without game database context."
        print(f"Warning: {warning}")
        logging.warning(warning)
        return {}

    game_database_map = {}

    for record in rows_to_records(rows):
        game_code = str(record.get("game_code", "")).strip().lower()

        if not game_code:
            continue

        clean_record = {
            key: value
            for key, value in record.items()
            if not key.startswith("_") and str(value).strip()
        }

        if game_code in game_database_map:
            logging.warning(
                "Duplicate game_code=%s found in %s. Keeping the first row.",
                game_code,
                GAME_DATABASE_SHEET,
            )
            continue

        game_database_map[game_code] = clean_record

    return game_database_map


def parse_generation_count(value: Any) -> int:
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError):
        count = 1

    return max(1, count)


def now_kst_iso() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).replace(microsecond=0).isoformat()


def now_kst_compact() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime("%Y%m%d%H%M%S")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "creative"


def get_game_info_for_brief(
    brief: dict[str, Any],
    game_database_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    game_code = str(brief.get("game_code", "")).strip().lower()

    if not game_code:
        warning = f"brief_id={brief.get('brief_id', '')} has no game_code. Using campaign brief only."
        print(f"Warning: {warning}")
        logging.warning(warning)
        return {}

    game_info = game_database_map.get(game_code, {})

    if not game_info:
        warning = f"game_code={game_code} was not found in {GAME_DATABASE_SHEET}. Using campaign brief only."
        print(f"Warning: {warning}")
        logging.warning(warning)

    return game_info


def build_game_database_guidance(game_info: dict[str, Any]) -> str:
    if not game_info:
        return "- No matching game database information was found. Use only the campaign brief."

    guidance_lines = []

    forbidden_items = [
        str(game_info.get(column, "")).strip()
        for column in FORBIDDEN_GAME_DATABASE_COLUMNS
        if str(game_info.get(column, "")).strip()
    ]

    if forbidden_items:
        guidance_lines.append(
            "- Absolutely do not use or imply these elements in any copy, image prompt, or video prompt: "
            + " | ".join(forbidden_items)
        )

    visual_items = [
        f"{column}: {str(game_info.get(column, '')).strip()}"
        for column in VISUAL_GAME_DATABASE_COLUMNS
        if str(game_info.get(column, "")).strip()
    ]

    if visual_items:
        guidance_lines.append(
            "- Actively reflect these game identity fields in image_prompt_en and video_prompt_en: "
            + " | ".join(visual_items)
        )

    guidance_lines.append(
        "- Use the game database information to make the ad copy, image prompt, and video prompt more specific to the game's genre, world, combat, characters, brand tone, and differentiators."
    )

    return "\n".join(guidance_lines)


def build_prompt(brief: dict[str, Any], game_info: dict[str, Any], generation_count: int) -> str:
    brief_payload = {key: value for key, value in brief.items() if not key.startswith("_")}
    game_payload = {key: value for key, value in game_info.items() if not key.startswith("_")}

    return f"""Generate exactly {generation_count} distinct ad creative variants from this campaign brief.

Campaign brief:
{json.dumps(brief_payload, ensure_ascii=False, indent=2)}

Game database information:
{json.dumps(game_payload, ensure_ascii=False, indent=2) if game_payload else "{}"}

Game database usage guidance:
{build_game_database_guidance(game_info)}

Source priority:
When game database information is provided, treat it as the authoritative source for the game's genre, tone, world setting, visual style, combat style, character direction, and prohibited elements.
Do not invent game features that conflict with the game database.
Use campaign brief information for the temporary campaign objective and promotion details.
Use game database information for the fixed product identity.

Rules:
- headline, primary_text, description, and cta must be written in the target language from the brief.
- image_prompt_en and video_prompt_en must be production-ready English prompts.
- image_prompt_kr and video_prompt_kr must be faithful Korean translations of the English prompts.
- negative_prompt must list risky or unwanted visual/text elements to avoid.
- localization_note must explain language/country nuance for human reviewers.
- compliance_check must be one of: passed, needs_review, failed.
- risk_level must be one of: low, medium, high.
- Actively use matching game database information in headline, primary_text, description, image_prompt_en, and video_prompt_en when it improves specificity.
- If do_not_use or forbidden_elements exist in the game database information, never use those words, themes, visual elements, claims, or implications.
- If visual_style, brand_tone, combat_style, or worldview exist in the game database information, reflect them clearly in image_prompt_en and video_prompt_en.
- Do not invent unavailable rewards, guaranteed outcomes, rankings, odds, or legal claims.
- Keep variants meaningfully different from each other."""


def parse_gemini_response(response: Any) -> list[dict[str, str]]:
    parsed = getattr(response, "parsed", None)

    if isinstance(parsed, dict):
        creatives = parsed.get("creatives", [])
    else:
        text = getattr(response, "text", "") or ""
        payload = json.loads(text)
        creatives = payload.get("creatives", [])

    if not isinstance(creatives, list):
        raise RuntimeError("Gemini response did not contain a creatives list.")

    return creatives


def generate_creatives_with_gemini(
    client: genai.Client,
    model: str,
    brief: dict[str, Any],
    game_info: dict[str, Any],
    generation_count: int,
) -> list[dict[str, str]]:
    prompt = build_prompt(brief, game_info, generation_count)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "system_instruction": SYSTEM_INSTRUCTION,
            "response_mime_type": "application/json",
            "response_json_schema": CREATIVE_RESPONSE_SCHEMA,
            "temperature": 1.0,
        },
    )

    creatives = parse_gemini_response(response)

    if len(creatives) < generation_count:
        raise RuntimeError(
            f"Gemini returned {len(creatives)} creatives, expected {generation_count}."
        )

    return creatives[:generation_count]


def build_generated_record(
    brief: dict[str, Any],
    creative: dict[str, Any],
    creative_index: int,
    created_at: str,
) -> dict[str, str]:
    brief_id = str(brief.get("brief_id", "brief")).strip()
    creative_id = f"crt_{slugify(brief_id)}_{now_kst_compact()}_{creative_index:02d}"

    record = {
        "creative_id": creative_id,
        "brief_id": brief_id,
        "created_at": created_at,
        "game_name": str(brief.get("game_name", "")).strip(),
        "game_code": str(brief.get("game_code", "")).strip(),
        "country": str(brief.get("country", "")).strip(),
        "language": str(brief.get("language", "")).strip(),
        "media": str(brief.get("media", "")).strip(),
        "platform": str(brief.get("platform", "")).strip(),
        "creative_type": str(brief.get("creative_type", "")).strip(),
        "creative_angle": str(brief.get("creative_angle", "")).strip(),
        "status": "draft",
        "reference_image": "auto",
        "text_overlay": "yes",
    }

    for field in CREATIVE_OUTPUT_FIELDS:
        record[field] = str(creative.get(field, "")).strip()

    if record["compliance_check"] not in {"passed", "needs_review", "failed"}:
        record["compliance_check"] = "needs_review"

    if record["risk_level"] not in {"low", "medium", "high"}:
        record["risk_level"] = "medium"

    return record


def records_to_rows(records: list[dict[str, str]], headers: list[str]) -> list[list[str]]:
    return [[record.get(header, "") for header in headers] for record in records]


def write_generated_rows(
    service: Any,
    spreadsheet_id: str,
    headers: list[str],
    records: list[dict[str, str]],
    start_row: int,
) -> None:
    if not records:
        return

    values = records_to_rows(records, headers)
    end_row = start_row + len(values) - 1
    end_col = column_letter(len(headers))

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(GENERATED_CREATIVES_SHEET)}!A{start_row}:{end_col}{end_row}",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def update_brief_status(service: Any, spreadsheet_id: str, row_number: int, status_value: str) -> None:
    rows = get_sheet_values(service, spreadsheet_id, CAMPAIGN_BRIEF_SHEET)

    if not rows:
        raise RuntimeError(f"{CAMPAIGN_BRIEF_SHEET} has no header row.")

    headers = [normalize_header(header) for header in rows[0]]

    if "status" not in headers:
        raise RuntimeError(f"{CAMPAIGN_BRIEF_SHEET} is missing status header.")

    status_col = headers.index("status") + 1
    status_col_letter = column_letter(status_col)

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(CAMPAIGN_BRIEF_SHEET)}!{status_col_letter}{row_number}",
        valueInputOption="USER_ENTERED",
        body={"values": [[status_value]]},
    ).execute()


def print_dry_run_records(brief: dict[str, Any], records: list[dict[str, str]]) -> None:
    print("=" * 80)
    print(f"DRY RUN brief_id={brief.get('brief_id', '')} generated_count={len(records)}")
    print(json.dumps(records, ensure_ascii=False, indent=2))


def main(dry_run: bool = False, max_briefs: int = 0) -> None:
    spreadsheet_id = get_spreadsheet_id()
    model = os.getenv("AI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    try:
        sheets_service = build_sheets_service()
        gemini_client = build_gemini_client()
        generated_headers = ensure_generated_headers(sheets_service, spreadsheet_id)
        game_database_map = get_game_database_map(sheets_service, spreadsheet_id)

        ready_briefs = get_ready_briefs(
            sheets_service,
            spreadsheet_id,
            max_briefs=max_briefs,
        )

        if not ready_briefs:
            print("No ready campaign briefs found.")
            logging.info("No ready campaign briefs found.")
            return

        print(f"Found {len(ready_briefs)} ready brief(s). model={model} dry_run={dry_run}")

        for brief in ready_briefs:
            brief_id = str(brief.get("brief_id", "")).strip()
            row_number = int(brief.get("_row_number", 0))

            try:
                generation_count = parse_generation_count(brief.get("generation_count"))

                if generation_count > 1:
                    print(
                        f"Warning: generation_count={generation_count}. "
                        f"02_generated_creatives will use rows {row_number}~{row_number + generation_count - 1}."
                    )

                generated_at = now_kst_iso()
                game_info = get_game_info_for_brief(brief, game_database_map)

                creatives = generate_creatives_with_gemini(
                    gemini_client,
                    model,
                    brief,
                    game_info,
                    generation_count,
                )

                records = [
                    build_generated_record(brief, creative, index, generated_at)
                    for index, creative in enumerate(creatives, start=1)
                ]

                if dry_run:
                    print_dry_run_records(brief, records)
                    continue

                write_generated_rows(
                    sheets_service,
                    spreadsheet_id,
                    generated_headers,
                    records,
                    row_number,
                )

                if row_number > 0:
                    update_brief_status(
                        sheets_service,
                        spreadsheet_id,
                        row_number,
                        "generated",
                    )

                print(
                    f"Generated {len(records)} creative(s) for brief_id={brief_id} "
                    f"at {GENERATED_CREATIVES_SHEET} row {row_number}"
                )

            except Exception as exc:
                print(f"Failed to process brief_id={brief_id}. Check {LOG_FILE}.")
                logging.exception("Failed to process brief_id=%s: %s", brief_id, exc)

    except Exception as exc:
        logging.exception("Gemini creative generation automation failed: %s", exc)
        raise


if __name__ == "__main__":
    load_dotenv(ROOT_DIR / ".env")
    setup_logging()
    args = parse_args()

    dry_run_value = args.dry_run or env_flag("DRY_RUN", False)

    if args.watch:
        print(f"Watching ready briefs every {args.interval} seconds...")

        while True:
            try:
                main(
                    dry_run=dry_run_value,
                    max_briefs=args.max_briefs,
                )
            except Exception as exc:
                print(f"Watch mode error: {exc}")
                logging.exception("Watch mode error: %s", exc)

            time.sleep(args.interval)

    else:
        main(
            dry_run=dry_run_value,
            max_briefs=args.max_briefs,
        )