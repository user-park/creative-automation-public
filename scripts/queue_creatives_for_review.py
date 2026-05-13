import argparse
import base64
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
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
GENERATED_CREATIVES_SHEET = "02_generated_creatives"
CREATIVE_REVIEW_SHEET = "03_creative_review"

GENERATED_REQUIRED_COLUMNS = [
    "creative_id",
    "brief_id",
    "status",
    "headline",
    "primary_text",
    "description",
    "cta",
    "image_prompt_en",
    "image_prompt_kr",
    "video_prompt_en",
    "video_prompt_kr",
]

CREATIVE_REVIEW_COLUMNS = [
    "review_id",
    "creative_id",
    "brief_id",
    "reviewer",
    "review_status",
    "review_comment",
    "final_headline",
    "final_primary_text",
    "final_description",
    "final_cta",
    "final_image_prompt_en",
    "final_image_prompt_kr",
    "final_video_prompt_en",
    "final_video_prompt_kr",
    "approval_date",
    "upload_ready",
]


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
        description="Move generated creatives with status=review into the human review queue."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rows that would be appended without writing to Google Sheets.",
    )
    parser.add_argument(
        "--max-creatives",
        type=int,
        default=0,
        help="Optional limit for creatives to queue. 0 means no limit.",
    )
    return parser.parse_args()


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_spreadsheet_id() -> str:
    spreadsheet_id = (
        os.getenv("GOOGLE_SPREADSHEET_ID")
        or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        or ""
    ).strip()

    if not spreadsheet_id:
        raise RuntimeError(
            "Spreadsheet ID was not found. Set GOOGLE_SPREADSHEET_ID in .env."
        )

    return spreadsheet_id


def get_google_credentials() -> service_account.Credentials:
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
        raise FileNotFoundError(
            "Google service account file was not found. "
            f"Resolved path: {credential_path}"
        )

    return service_account.Credentials.from_service_account_file(
        str(credential_path),
        scopes=SCOPES,
    )


def build_sheets_service() -> Any:
    credentials = get_google_credentials()
    return build("sheets", "v4", credentials=credentials)


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
    max_columns: int = 80,
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

    headers = rows[0]
    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        padded_row = row + [""] * (len(headers) - len(row))
        record = dict(zip(headers, padded_row))
        record["_row_number"] = row_number
        records.append(record)
    return records


def require_headers(
    actual_headers: list[str],
    required_headers: list[str],
    sheet_name: str,
) -> None:
    missing = [header for header in required_headers if header not in actual_headers]
    if missing:
        raise RuntimeError(
            f"{sheet_name} is missing required headers: {', '.join(missing)}"
        )


def get_review_status_creatives(
    service: Any,
    spreadsheet_id: str,
    max_creatives: int = 0,
) -> list[dict[str, Any]]:
    rows = get_sheet_values(service, spreadsheet_id, GENERATED_CREATIVES_SHEET)
    if not rows:
        raise RuntimeError(f"{GENERATED_CREATIVES_SHEET} has no header row.")

    headers = rows[0]
    require_headers(headers, GENERATED_REQUIRED_COLUMNS, GENERATED_CREATIVES_SHEET)

    creatives = [
        record
        for record in rows_to_records(rows)
        if str(record.get("status", "")).strip().lower() == "review"
    ]

    if max_creatives > 0:
        creatives = creatives[:max_creatives]

    return creatives


def get_review_headers_and_existing_ids(
    service: Any,
    spreadsheet_id: str,
) -> tuple[list[str], set[str]]:
    rows = get_sheet_values(service, spreadsheet_id, CREATIVE_REVIEW_SHEET)
    if not rows:
        raise RuntimeError(f"{CREATIVE_REVIEW_SHEET} has no header row.")

    headers = rows[0]
    require_headers(headers, CREATIVE_REVIEW_COLUMNS, CREATIVE_REVIEW_SHEET)

    existing_creative_ids = {
        str(record.get("creative_id", "")).strip()
        for record in rows_to_records(rows)
        if str(record.get("creative_id", "")).strip()
    }

    return headers, existing_creative_ids


def now_kst_compact() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime("%Y%m%d%H%M%S")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "creative"


def build_review_record(
    creative: dict[str, Any],
    reviewer: str,
    record_index: int,
) -> dict[str, str]:
    creative_id = str(creative.get("creative_id", "")).strip()
    return {
        "review_id": f"rev_{slugify(creative_id)}_{now_kst_compact()}_{record_index:02d}",
        "creative_id": creative_id,
        "brief_id": str(creative.get("brief_id", "")).strip(),
        "reviewer": reviewer,
        "review_status": "pending",
        "review_comment": "",
        "final_headline": str(creative.get("headline", "")).strip(),
        "final_primary_text": str(creative.get("primary_text", "")).strip(),
        "final_description": str(creative.get("description", "")).strip(),
        "final_cta": str(creative.get("cta", "")).strip(),
        "final_image_prompt_en": str(creative.get("image_prompt_en", "")).strip(),
        "final_image_prompt_kr": str(creative.get("image_prompt_kr", "")).strip(),
        "final_video_prompt_en": str(creative.get("video_prompt_en", "")).strip(),
        "final_video_prompt_kr": str(creative.get("video_prompt_kr", "")).strip(),
        "approval_date": "",
        "upload_ready": "no",
    }


def records_to_rows(records: list[dict[str, str]], headers: list[str]) -> list[list[str]]:
    return [[record.get(header, "") for header in headers] for record in records]


def append_review_rows(
    service: Any,
    spreadsheet_id: str,
    headers: list[str],
    records: list[dict[str, str]],
) -> None:
    if not records:
        return

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(CREATIVE_REVIEW_SHEET)}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": records_to_rows(records, headers)},
    ).execute()


def print_dry_run_records(records: list[dict[str, str]]) -> None:
    print("=" * 80)
    print(f"DRY RUN review queue rows to append: {len(records)}")
    print(json.dumps(records, ensure_ascii=False, indent=2))


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    setup_logging()

    args = parse_args()
    dry_run = args.dry_run or env_flag("DRY_RUN", False)
    spreadsheet_id = get_spreadsheet_id()
    reviewer = os.getenv("DEFAULT_REVIEWER", "").strip()

    try:
        sheets_service = build_sheets_service()
        review_headers, existing_creative_ids = get_review_headers_and_existing_ids(
            sheets_service,
            spreadsheet_id,
        )
        review_status_creatives = get_review_status_creatives(
            sheets_service,
            spreadsheet_id,
            max_creatives=args.max_creatives,
        )

        records = []
        for creative in review_status_creatives:
            creative_id = str(creative.get("creative_id", "")).strip()
            if not creative_id:
                logging.warning("Skipped generated creative with empty creative_id.")
                continue
            if creative_id in existing_creative_ids:
                logging.info(
                    "Skipped duplicate creative_id=%s already in review queue.",
                    creative_id,
                )
                continue
            records.append(build_review_record(creative, reviewer, len(records) + 1))

        if not records:
            print("No new review queue rows to append.")
            logging.info("No new review queue rows to append.")
            return

        if dry_run:
            print_dry_run_records(records)
            logging.info("Dry run prepared %s review queue row(s).", len(records))
            return

        append_review_rows(sheets_service, spreadsheet_id, review_headers, records)
        print(f"Added {len(records)} creative(s) to {CREATIVE_REVIEW_SHEET}.")
        print("Next upload condition: review_status=approved AND upload_ready=yes")
        logging.info("Added %s creative(s) to %s.", len(records), CREATIVE_REVIEW_SHEET)
    except Exception as exc:
        logging.exception("Review queue automation failed: %s", exc)
        raise


if __name__ == "__main__":
    main()
