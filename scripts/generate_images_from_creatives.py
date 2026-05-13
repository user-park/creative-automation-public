import os
import time
import random
import argparse
from pathlib import Path
from datetime import datetime
from io import BytesIO

import gspread
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image


load_dotenv()

SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-image-preview")
IMAGE_OUTPUT_DIR = os.getenv("IMAGE_OUTPUT_DIR", "./outputs/images")

SHEET_NAME = "02_generated_creatives"
REFERENCE_IMAGE_DIR = "./reference_images"


def now_text():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def safe_filename(text):
    return str(text).strip().replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")


def get_sheet():
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_JSON)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(SHEET_NAME)


def get_headers(sheet):
    return sheet.row_values(1)


def ensure_headers(sheet, required_headers):
    headers = get_headers(sheet)

    for header in required_headers:
        if header not in headers:
            next_col = len(headers) + 1

            if next_col > sheet.col_count:
                sheet.add_cols(1)

            sheet.update_cell(1, next_col, header)
            headers.append(header)

    return headers


def col_index(headers, name):
    if name not in headers:
        raise ValueError(f"{name} 컬럼을 찾을 수 없습니다.")
    return headers.index(name) + 1


def update_cell_by_header(sheet, headers, row_number, header, value):
    if header not in headers:
        return

    col = col_index(headers, header)
    sheet.update_cell(row_number, col, value)


def read_image_bytes(image_path):
    with open(image_path, "rb") as f:
        return f.read()


def get_mime_type(image_path):
    suffix = image_path.suffix.lower()

    if suffix == ".png":
        return "image/png"
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"

    return "image/png"


def find_reference_image(game_code, reference_image_value):
    game_folder = Path(REFERENCE_IMAGE_DIR) / safe_filename(game_code)

    if not game_folder.exists():
        raise FileNotFoundError(f"참조 이미지 폴더가 없습니다: {game_folder}")

    image_files = []

    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
        image_files.extend(game_folder.glob(ext))

    image_files = [
        file for file in image_files
        if not file.name.lower().startswith("logo")
        and "확률형" not in file.name
        and "probability" not in file.name.lower()
    ]

    if not image_files:
        raise FileNotFoundError(f"참조 일러스트 이미지가 없습니다: {game_folder}")

    reference_image_value = str(reference_image_value or "auto").strip()

    if reference_image_value.lower() != "auto":
        selected = game_folder / reference_image_value

        if selected.exists():
            return selected

        raise FileNotFoundError(f"지정한 참조 이미지를 찾을 수 없습니다: {selected}")

    return random.choice(image_files)


def find_logo_image(game_code):
    game_folder = Path(REFERENCE_IMAGE_DIR) / safe_filename(game_code)

    possible_logo_names = [
        "logo.png",
        "logo.jpg",
        "logo.jpeg",
        "logo.webp",
    ]

    for logo_name in possible_logo_names:
        logo_path = game_folder / logo_name

        if logo_path.exists():
            return logo_path

    return None


def find_probability_badge(game_code, country):
    if str(country).strip().upper() != "KR":
        return None

    game_folder = Path(REFERENCE_IMAGE_DIR) / safe_filename(game_code)

    possible_badge_names = [
        "확률형포함.png",
        "확률형포함.PNG",
        "확률형포함.jpg",
        "확률형포함.jpeg",
        "probability_notice.png",
        "probability_notice.jpg",
        "probability_notice.jpeg",
    ]

    for badge_name in possible_badge_names:
        badge_path = game_folder / badge_name

        if badge_path.exists():
            return badge_path

    return None


def build_edit_prompt(row, has_logo=False):
    headline = str(row.get("headline", "")).strip()
    image_prompt_en = str(row.get("image_prompt_en", "")).strip()
    text_overlay = str(row.get("text_overlay", "")).strip().lower()

    if not text_overlay:
        text_overlay = "yes"

    prompt = f"""
Use the provided reference illustration as the ONLY base visual source.

Strictly preserve the original IP character identity:
- same face structure
- same hairstyle
- same costume and armor design
- same weapon design
- same color palette
- same illustration style
- same premium MMORPG visual identity

Do NOT create a new character.
Do NOT redesign the costume.
Do NOT change the IP style.
Do NOT replace the character with a generic fantasy character.

Modify only the following based on the advertising direction:
- pose
- facial expression
- camera composition
- background
- lighting
- action effects
- atmosphere
- advertising layout

Advertising direction from the creative sheet:
{image_prompt_en}

Create a polished vertical mobile game ad key visual.
Premium AAA dark fantasy MMORPG advertising style.
High detail, cinematic lighting, strong contrast, clear focal character.
"""

    if has_logo:
        prompt += """

The second provided image is the official game logo.

Logo requirements:
- include the official game logo in the final image
- preserve the original logo design exactly
- do not redesign, distort, redraw, or translate the logo
- place the logo in a clean safe area
- keep the logo highly readable
- use premium mobile game ad composition
"""

    if text_overlay == "yes" and headline:
        prompt += f"""

Add readable headline text inside the image:
"{headline}"

Typography requirements:
- bold cinematic MMORPG advertising headline
- high readability
- premium fantasy UI style
- placed naturally without covering the character face
- clean spacing
- no broken letters
- no random extra text
"""
    else:
        prompt += """

Do not add headline text overlay.
Do not add random letters, watermarks, or unnecessary UI text.
"""

    return prompt.strip()


def overlay_probability_badge(output_path, badge_path):
    base = Image.open(output_path).convert("RGBA")
    badge = Image.open(badge_path).convert("RGBA")

    base_width, base_height = base.size

    target_badge_width = int(base_width * 0.22)
    badge_ratio = badge.height / badge.width
    target_badge_height = int(target_badge_width * badge_ratio)

    badge = badge.resize(
        (target_badge_width, target_badge_height),
        Image.LANCZOS,
    )

    margin_x = int(base_width * 0.035)
    margin_y = int(base_height * 0.025)

    x = base_width - target_badge_width - margin_x
    y = base_height - target_badge_height - margin_y

    base.alpha_composite(badge, (x, y))
    base.save(output_path)


def generate_image_from_reference(
    reference_image_path,
    logo_image_path,
    prompt,
    output_path,
):
    client = genai.Client(api_key=GEMINI_API_KEY)

    reference_bytes = read_image_bytes(reference_image_path)
    reference_mime = get_mime_type(reference_image_path)

    contents_parts = [
        types.Part.from_bytes(
            data=reference_bytes,
            mime_type=reference_mime,
        )
    ]

    if logo_image_path:
        logo_bytes = read_image_bytes(logo_image_path)
        logo_mime = get_mime_type(logo_image_path)

        contents_parts.append(
            types.Part.from_bytes(
                data=logo_bytes,
                mime_type=logo_mime,
            )
        )

    contents_parts.append(prompt)

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=contents_parts,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"]
        ),
    )

    generated_image_bytes = None

    for candidate in response.candidates:
        for part in candidate.content.parts:
            if getattr(part, "inline_data", None):
                generated_image_bytes = part.inline_data.data
                break

        if generated_image_bytes:
            break

    if not generated_image_bytes:
        raise RuntimeError("Gemini 응답에서 이미지 데이터를 찾지 못했습니다.")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(generated_image_bytes)


def process_approved_images(max_images=None):
    sheet = get_sheet()

    headers = ensure_headers(
        sheet,
        [
            "reference_image",
            "text_overlay",
            "image_file",
            "image_status",
            "image_generated_at",
            "image_error",
        ],
    )

    records = sheet.get_all_records()
    processed = 0

    for idx, row in enumerate(records, start=2):
        status = str(row.get("status", "")).strip().lower()

        if status != "approved":
            continue

        image_file = str(row.get("image_file", "")).strip()

        if image_file:
            continue

        creative_id = row.get("creative_id") or f"row_{idx}"
        game_code = row.get("game_code") or "unknown_game"
        country = row.get("country") or "unknown_country"

        reference_image_value = str(row.get("reference_image", "")).strip()

        if not reference_image_value:
            reference_image_value = "auto"
            update_cell_by_header(sheet, headers, idx, "reference_image", "auto")

        text_overlay_value = str(row.get("text_overlay", "")).strip()

        if not text_overlay_value:
            update_cell_by_header(sheet, headers, idx, "text_overlay", "yes")
            row["text_overlay"] = "yes"

        filename = f"{safe_filename(creative_id)}.png"

        output_dir = (
            Path(IMAGE_OUTPUT_DIR)
            / safe_filename(game_code)
            / safe_filename(country)
        )

        output_path = output_dir / filename

        try:
            print(f"Generating image for row {idx}: {creative_id}")

            update_cell_by_header(sheet, headers, idx, "status", "generating")
            update_cell_by_header(sheet, headers, idx, "image_status", "generating")
            update_cell_by_header(sheet, headers, idx, "image_error", "")

            reference_image_path = find_reference_image(
                game_code,
                reference_image_value,
            )

            logo_image_path = find_logo_image(game_code)
            probability_badge_path = find_probability_badge(game_code, country)

            prompt = build_edit_prompt(
                row,
                has_logo=logo_image_path is not None,
            )

            generate_image_from_reference(
                reference_image_path,
                logo_image_path,
                prompt,
                output_path,
            )

            if probability_badge_path:
                overlay_probability_badge(output_path, probability_badge_path)

            update_cell_by_header(sheet, headers, idx, "status", "generated")
            update_cell_by_header(sheet, headers, idx, "image_status", "generated")
            update_cell_by_header(sheet, headers, idx, "image_file", str(output_path))
            update_cell_by_header(sheet, headers, idx, "image_generated_at", now_text())
            update_cell_by_header(sheet, headers, idx, "image_error", "")
            update_cell_by_header(sheet, headers, idx, "reference_image", reference_image_path.name)

            print(f"Saved: {output_path}")

            processed += 1

        except Exception as e:
            update_cell_by_header(sheet, headers, idx, "status", "failed")
            update_cell_by_header(sheet, headers, idx, "image_status", "failed")
            update_cell_by_header(sheet, headers, idx, "image_error", str(e))

            print(f"Failed row {idx}: {e}")

        if max_images and processed >= max_images:
            break

    return processed


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)

    args = parser.parse_args()

    if args.watch:
        print(f"Watching approved creatives every {args.interval} seconds...")

        while True:
            processed = process_approved_images(max_images=args.max_images)

            if processed:
                print(f"Processed {processed} image(s).")

            time.sleep(args.interval)

    else:
        processed = process_approved_images(max_images=args.max_images)
        print(f"Done. Processed {processed} image(s).")


if __name__ == "__main__":
    main()