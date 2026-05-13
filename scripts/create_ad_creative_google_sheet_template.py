from __future__ import annotations

import base64
import json
import os
from google.oauth2 import service_account
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install packages with: pip install -r requirements.txt"
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[1]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

STATUS_VALUES = ["draft", "review", "approved", "rejected", "uploaded", "active", "paused"]
MEDIA_VALUES = ["meta_ads", "google_ads", "naver_gfa", "dable", "tiktok_ads", "unity_ads", "applovin"]
PLATFORM_VALUES = ["android", "ios", "pc", "cross_platform"]
CREATIVE_TYPE_VALUES = ["ad_copy", "image_prompt", "video_prompt", "video_script", "storyboard", "ugc_script", "playable_concept"]
CAMPAIGN_GOAL_VALUES = ["app_install", "purchase", "pre_registration", "retention", "brand_awareness", "event_participation"]
TONE_VALUES = ["epic", "casual", "funny", "dramatic", "competitive", "premium", "urgent", "nostalgic"]


def col(
    name: str,
    description: str,
    data_type: str,
    required: bool,
    example: str,
    allowed_values: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "data_type": data_type,
        "required": required,
        "example": example,
        "allowed_values": allowed_values or [],
    }


SHEET_DEFINITIONS: list[dict[str, Any]] = [
    {
        "title": "01_campaign_brief",
        "columns": [
            col("brief_id", "Campaign brief unique ID.", "string", True, "brf_cabal_jp_gw_202605_001"),
            col("created_at", "Brief creation datetime in ISO 8601 format.", "datetime", True, "2026-05-07T10:00:00+09:00"),
            col("created_by", "Brief creator email or name.", "string", True, "global_marketer@example.com"),
            col("game_name", "Advertised game name.", "string", True, "CABAL Mobile"),
            col("game_code", "Internal game code.", "string", True, "cabal_mobile"),
            col("campaign_name", "Campaign name for internal tracking.", "string", True, "JP Golden Week Returning Users Campaign"),
            col("campaign_goal", "Primary marketing goal.", "enum", True, "retention", CAMPAIGN_GOAL_VALUES),
            col("country", "Target country code.", "string", True, "JP"),
            col("language", "Creative language code.", "string", True, "ja"),
            col("media", "Target ad media channel.", "enum", True, "meta_ads", MEDIA_VALUES),
            col("platform", "Target user device platform.", "enum", True, "android", PLATFORM_VALUES),
            col("target_audience", "Main target audience description.", "text", True, "Japanese players who previously played CABAL Mobile and may return during Golden Week."),
            col("user_segment", "Detailed user segment.", "string", True, "returning_users_30d_plus"),
            col("usp_1", "Unique selling point 1.", "text", True, "Nostalgic CABAL action and combo combat on mobile."),
            col("usp_2", "Unique selling point 2.", "text", False, "Golden Week is a good timing to return and catch up."),
            col("usp_3", "Unique selling point 3.", "text", False, "Fast growth events and rewards help returning players restart smoothly."),
            col("promotion_1", "Promotion message 1.", "text", False, "Golden Week comeback rewards available for returning players."),
            col("promotion_2", "Promotion message 2.", "text", False, "Login during the campaign period to receive growth support items."),
            col("promotion_3", "Promotion message 3.", "text", False, "Limited-time event missions for quick progression."),
            col("landing_url", "Ad landing URL.", "url", True, "https://example.com/cabal-mobile-jp-gw"),
            col("creative_type", "Creative output type to generate.", "enum", True, "video_prompt", CREATIVE_TYPE_VALUES),
            col("tone", "Copy tone and manner.", "enum", True, "nostalgic", TONE_VALUES),
            col("creative_angle", "Creative angle for generation.", "string", True, "golden_week_comeback"),
            col("reference_note", "Reference assets, prior ads, or creative direction notes.", "text", False, "Emphasize returning to the battlefield during Golden Week with familiar CABAL combat energy."),
            col("compliance_note", "Legal, policy, brand, or forbidden-expression notes.", "text", False, "Avoid guaranteed reward claims, excessive urgency, and misleading free item wording."),
            col("generation_count", "Number of creative variants to generate.", "integer", True, "3"),
            col("status", "Brief processing status. Generation automation reads rows where status is draft.", "enum", True, "draft", STATUS_VALUES),
        ],
    },
    {
        "title": "02_generated_creatives",
        "columns": [
            col("creative_id", "Generated creative unique ID.", "string", True, "crt_cabal_jp_gw_202605_001_01"),
            col("brief_id", "Source campaign brief ID.", "string", True, "brf_cabal_jp_gw_202605_001"),
            col("created_at", "Creative generation datetime in ISO 8601 format.", "datetime", True, "2026-05-07T10:05:00+09:00"),
            col("game_name", "Advertised game name.", "string", True, "CABAL Mobile"),
            col("game_code", "Internal game code.", "string", True, "cabal_mobile"),
            col("country", "Target country code.", "string", True, "JP"),
            col("language", "Creative language code.", "string", True, "ja"),
            col("media", "Target ad media channel.", "enum", True, "meta_ads", MEDIA_VALUES),
            col("platform", "Target user device platform.", "enum", True, "android", PLATFORM_VALUES),
            col("creative_type", "Generated creative type.", "enum", True, "video_prompt", CREATIVE_TYPE_VALUES),
            col("creative_angle", "Creative angle used for generation.", "string", True, "golden_week_comeback"),
            col("headline", "Generated ad headline.", "text", True, "GW is the time to return to CABAL"),
            col("primary_text", "Generated primary ad copy.", "text", True, "Feel the nostalgic combo action again during Golden Week. Return to CABAL Mobile and restart your adventure."),
            col("description", "Generated ad description.", "text", False, "A comeback campaign for returning users."),
            col("cta", "Generated call-to-action text.", "string", True, "Return Now"),
            col("image_prompt_en", "English prompt for image generation.", "text", False, "A cinematic mobile MMORPG ad image showing a returning warrior stepping back into a bright fantasy battlefield during Japan Golden Week, dynamic combo action, premium game UI feel, no gore."),
            col("image_prompt_kr", "Korean prompt for image generation.", "text", False, "일본 골든위크 분위기 속 밝은 판타지 전장으로 복귀하는 전사를 보여주는 시네마틱 모바일 MMORPG 광고 이미지, 역동적인 콤보 액션, 고급 게임 UI 느낌, 고어 없음."),
            col("video_prompt_en", "English prompt for video generation.", "text", False, "Create a 15-second vertical video: a former CABAL Mobile player returns during Golden Week, sees comeback rewards, enters a fast combo battle, and ends with a clear return CTA."),
            col("video_prompt_kr", "Korean prompt for video generation.", "text", False, "15초 세로형 영상 생성: CABAL Mobile 휴면 유저가 골든위크에 복귀하고, 복귀 보상을 확인한 뒤 빠른 콤보 전투에 진입하며 명확한 복귀 CTA로 마무리."),
            col("negative_prompt", "Elements to avoid in image or video generation.", "text", False, "low quality, blurry, gore, real celebrity, copyrighted character, misleading reward guarantee"),
            col("localization_note", "Localization note for target country and language.", "text", False, "Use natural Japanese for returning players. Keep the tone nostalgic but action-oriented."),
            col("compliance_check", "Automated compliance check result.", "enum", True, "needs_review", ["not_checked", "passed", "needs_review", "failed"]),
            col("risk_level", "Policy or brand risk level.", "enum", True, "medium", ["low", "medium", "high"]),
            col("status", "Creative processing status before human review.", "enum", True, "review", STATUS_VALUES),
        ],
    },
    {
        "title": "03_creative_review",
        "columns": [
            col("review_id", "Creative review unique ID.", "string", True, "rev_cabal_jp_gw_202605_001_01"),
            col("creative_id", "Creative ID being reviewed.", "string", True, "crt_cabal_jp_gw_202605_001_01"),
            col("brief_id", "Source campaign brief ID.", "string", True, "brf_cabal_jp_gw_202605_001"),
            col("reviewer", "Reviewer name or email.", "string", True, "reviewer@example.com"),
            col("review_status", "Human review status. Upload automation must only pass approved rows.", "enum", True, "pending", ["pending", "approved", "rejected"]),
            col("review_comment", "Human review comment or rejection reason.", "text", False, ""),
            col("final_headline", "Final approved headline.", "text", True, "GW is the time to return to CABAL"),
            col("final_primary_text", "Final approved primary ad copy.", "text", True, "Feel the nostalgic combo action again during Golden Week. Return to CABAL Mobile and restart your adventure."),
            col("final_description", "Final approved ad description.", "text", False, "A comeback campaign for returning users."),
            col("final_cta", "Final approved CTA text.", "string", True, "Return Now"),
            col("final_image_prompt_en", "Final approved English image prompt.", "text", False, "A cinematic mobile MMORPG ad image showing a returning warrior stepping back into a bright fantasy battlefield during Japan Golden Week, dynamic combo action, premium game UI feel, no gore."),
            col("final_image_prompt_kr", "Final approved Korean image prompt.", "text", False, "일본 골든위크 분위기 속 밝은 판타지 전장으로 복귀하는 전사를 보여주는 시네마틱 모바일 MMORPG 광고 이미지, 역동적인 콤보 액션, 고급 게임 UI 느낌, 고어 없음."),
            col("final_video_prompt_en", "Final approved English video prompt.", "text", False, "Create a 15-second vertical video: a former CABAL Mobile player returns during Golden Week, sees comeback rewards, enters a fast combo battle, and ends with a clear return CTA."),
            col("final_video_prompt_kr", "Final approved Korean video prompt.", "text", False, "15초 세로형 영상 생성: CABAL Mobile 휴면 유저가 골든위크에 복귀하고, 복귀 보상을 확인한 뒤 빠른 콤보 전투에 진입하며 명확한 복귀 CTA로 마무리."),
            col("approval_date", "Approval or rejection date.", "date", False, ""),
            col("upload_ready", "Whether this row is allowed to pass to automatic upload. Required upload condition: review_status=approved and upload_ready=yes.", "enum", True, "no", ["yes", "no"]),
        ],
    },
]


def column_letter(column_count: int) -> str:
    result = ""
    while column_count:
        column_count, remainder = divmod(column_count - 1, 26)
        result = chr(65 + remainder) + result
    return result


def quote_sheet_name(sheet_name: str) -> str:
    return "'" + sheet_name.replace("'", "''") + "'"


def column_note(column: dict[str, Any]) -> str:
    lines = [
        f"description: {column['description']}",
        f"data_type: {column['data_type']}",
        f"required: {'yes' if column['required'] else 'no'}",
        f"example_value: {column['example']}",
    ]
    if column["allowed_values"]:
        lines.append("allowed_values: " + ", ".join(column["allowed_values"]))
    return "\n".join(lines)


def get_credentials():

    credential_path_value = (
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )

    print("ENV PATH:", credential_path_value)

    if not credential_path_value:
        raise RuntimeError(
            "Google service account file path was not found. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON=./credentials/service-account.json"
        )

    credential_path = Path(credential_path_value).expanduser()
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


def create_spreadsheet_if_needed(service: Any) -> str:
    spreadsheet_id = (
        os.getenv("GOOGLE_SPREADSHEET_ID")
        or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        or ""
    ).strip()
    if spreadsheet_id:
        return spreadsheet_id

    title = os.getenv("GOOGLE_SHEETS_TITLE", "global_game_ad_creative_mvp_template")
    response = (
        service.spreadsheets()
        .create(
            body={
                "properties": {"title": title, "locale": "en_US", "timeZone": "Asia/Seoul"},
                "sheets": [{"properties": {"title": sheet["title"]}} for sheet in SHEET_DEFINITIONS],
            },
            fields="spreadsheetId,spreadsheetUrl",
        )
        .execute()
    )
    print(f"Created spreadsheet: {response['spreadsheetUrl']}")
    return response["spreadsheetId"]



def get_sheet_ids(service: Any, spreadsheet_id: str) -> dict[str, int]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in metadata.get("sheets", [])
    }


def ensure_sheets(service: Any, spreadsheet_id: str) -> dict[str, int]:
    sheet_ids = get_sheet_ids(service, spreadsheet_id)
    requests = [
        {"addSheet": {"properties": {"title": sheet["title"]}}}
        for sheet in SHEET_DEFINITIONS
        if sheet["title"] not in sheet_ids
    ]
    if requests:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
        sheet_ids = get_sheet_ids(service, spreadsheet_id)
    return sheet_ids


def write_headers_and_examples(service: Any, spreadsheet_id: str) -> None:
    data = []
    for sheet in SHEET_DEFINITIONS:
        columns = sheet["columns"]
        last_column = column_letter(len(columns))
        data.append(
            {
                "range": f"{quote_sheet_name(sheet['title'])}!A1:{last_column}2",
                "values": [
                    [column["name"] for column in columns],
                    [column["example"] for column in columns],
                ],
            }
        )

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()


def build_formatting_requests(sheet_ids: dict[str, int]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    for sheet in SHEET_DEFINITIONS:
        sheet_id = sheet_ids[sheet["title"]]
        columns = sheet["columns"]
        column_count = len(columns)

        requests.extend(
            [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": column_count},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.12, "green": 0.22, "blue": 0.34},
                                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                "horizontalAlignment": "CENTER",
                                "wrapStrategy": "WRAP",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,wrapStrategy)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": column_count},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.95, "green": 0.97, "blue": 0.99}, "wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                        "fields": "userEnteredFormat(backgroundColor,wrapStrategy,verticalAlignment)",
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": column_count}
                    }
                },
                {
                    "updateCells": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": column_count},
                        "rows": [{"values": [{"note": column_note(column)} for column in columns]}],
                        "fields": "note",
                    }
                },
            ]
        )

        for index, column in enumerate(columns):
            allowed_values = column["allowed_values"]
            if not allowed_values:
                continue
            requests.append(
                {
                    "setDataValidation": {
                        "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": index, "endColumnIndex": index + 1},
                        "rule": {
                            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": value} for value in allowed_values]},
                            "inputMessage": "Allowed values: " + ", ".join(allowed_values),
                            "strict": True,
                            "showCustomUi": True,
                        },
                    }
                }
            )

    return requests


def apply_formatting(service: Any, spreadsheet_id: str, sheet_ids: dict[str, int]) -> None:
    requests = build_formatting_requests(sheet_ids)
    if requests:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def read_draft_campaign_briefs(service: Any, spreadsheet_id: str) -> list[dict[str, str]]:
    sheet = next(item for item in SHEET_DEFINITIONS if item["title"] == "01_campaign_brief")
    headers = [column["name"] for column in sheet["columns"]]
    last_column = column_letter(len(headers))
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{quote_sheet_name('01_campaign_brief')}!A1:{last_column}")
        .execute()
    )

    rows = response.get("values", [])
    if len(rows) < 2:
        return []

    sheet_headers = rows[0]
    records = []
    for row in rows[1:]:
        padded_row = row + [""] * (len(sheet_headers) - len(row))
        record = dict(zip(sheet_headers, padded_row))
        if record.get("status") == "draft":
            records.append(record)
    return records


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    credentials = get_credentials()
    service = build("sheets", "v4", credentials=credentials)

    spreadsheet_id = create_spreadsheet_if_needed(service)
    sheet_ids = ensure_sheets(service, spreadsheet_id)
    write_headers_and_examples(service, spreadsheet_id)
    apply_formatting(service, spreadsheet_id, sheet_ids)

    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    draft_count = len(read_draft_campaign_briefs(service, spreadsheet_id))

    print("Google Sheets template is ready.")
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Spreadsheet URL: {spreadsheet_url}")
    print(f"Draft campaign briefs ready for generation: {draft_count}")
    print("Upload automation condition: review_status=approved AND upload_ready=yes")


if __name__ == "__main__":
    main()
