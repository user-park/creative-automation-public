# Creative Automation Public

마케팅 광고 소재의 카피, 이미지 프롬프트, 영상 프롬프트, 이미지 생성을 자동화하기 위한 팀원 공유용 프로젝트입니다.

## 기본 사용 방법

1. `watch_automation.bat` 파일을 실행합니다.
2. 검은색 자동화 창이 열리면 닫지 말고 그대로 유지합니다.
3. Google Sheets의 `01_campaign_brief` 시트에 광고 소재 요청 내용을 입력합니다.
4. `game_code`, `campaign_goal`, `tone` 입력 시 `promotion_1~3`이 자동 생성됩니다.
5. 광고 카피와 프롬프트를 생성하려면 `01_campaign_brief` 시트의 `status`를 `ready`로 변경합니다.
6. 자동화가 실행되면 `02_generated_creatives` 시트에 광고 카피와 이미지/영상 프롬프트가 생성됩니다.
7. `02_generated_creatives` 시트에서 결과를 확인합니다.
8. 이미지로 생성할 항목의 `status`를 `approved`로 변경합니다.
9. 조건이 맞으면 이미지가 자동 생성되며, 생성된 이미지는 `outputs/images` 폴더에 저장됩니다.

## 수동 실행이 필요할 때

자동 감시 모드를 사용하지 않고 직접 실행하고 싶을 때는 아래 파일을 실행합니다.

- `1_generate_creatives.bat`
  `01_campaign_brief` 시트의 `ready` 항목을 기준으로 광고 카피와 프롬프트만 생성합니다.

- `2_generate_images.bat`
  `02_generated_creatives` 시트에서 `approved` 상태인 항목만 이미지로 생성합니다.

- `watch_automation.bat`
  Google Sheets를 계속 감시하면서 카피/프롬프트 생성과 이미지 생성을 자동으로 실행합니다.

## 최초 설정 방법

1. 이 폴더를 다운로드합니다.
2. Python을 설치합니다.
3. 터미널에서 아래 명령어를 실행해 필요한 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

4. `.env.example` 파일을 복사해서 `.env` 파일로 이름을 바꿉니다.
5. `.env` 파일 안의 값을 본인 환경에 맞게 입력합니다.

```env
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service-account.json
GEMINI_API_KEY=your_gemini_api_key
IMAGE_MODEL=gemini-3.1-flash-image-preview
IMAGE_OUTPUT_DIR=./outputs/images
```

6. `credentials` 폴더를 만들고, Google 서비스 계정 JSON 파일을 `service-account.json` 이름으로 넣습니다.
7. Google Sheets 파일을 서비스 계정 이메일에 공유합니다.
8. `watch_automation.bat`을 실행합니다.

## 폴더 구조

```txt
creative-automation-public/
├─ reference_images/
│  ├─ CABAL_MOBILE_JP/
│  ├─ CABAL_ONLINE_KR/
│  └─ CAT_CAFE_KR/
├─ scripts/
│  ├─ create_ad_creative_google_sheet_template.py
│  ├─ generate_creatives_from_brief.py
│  ├─ generate_images_from_creatives.py
│  ├─ queue_creatives_for_review.py
│  └─ watch_automation.py
├─ .env.example
├─ .gitignore
├─ 1_generate_creatives.bat
├─ 2_generate_images.bat
├─ requirements.txt
├─ watch_automation.bat
└─ README.md
```

## 이미지 생성 기준

이미지는 `02_generated_creatives` 시트에서 아래 조건을 만족할 때 생성됩니다.

```txt
status = approved
image_file = 비어 있음
```

이미지가 생성되면 자동으로 아래 값이 입력됩니다.

```txt
status = generated
image_status = generated
image_file = 로컬 저장 경로
image_generated_at = 생성 시간
```

## 참고 이미지 사용 규칙

이미지 생성 시 `reference_images` 폴더 안의 게임별 폴더를 기준으로 참조 이미지를 사용합니다.

예시:

```txt
reference_images/
├─ CABAL_MOBILE_JP/
├─ CABAL_ONLINE_KR/
└─ CAT_CAFE_KR/
```

각 게임 폴더에는 아래 파일을 넣을 수 있습니다.

```txt
일러스트 이미지
logo.png
확률형포함.png
```

`logo.png`가 있으면 이미지 생성 시 로고를 함께 반영합니다.

국가가 `KR`인 경우, `확률형포함.png` 또는 `probability_notice.png` 파일이 있으면 생성된 이미지 우측 하단에 자동으로 합성됩니다.

## 주의사항

- 자동화 창을 닫으면 자동화가 중지됩니다.
- `.env` 파일은 절대 GitHub에 업로드하지 않습니다.
- `credentials` 폴더와 서비스 계정 JSON 파일은 절대 GitHub에 업로드하지 않습니다.
- Gemini API 키는 외부에 공유하지 않습니다.
- 이미지 생성이 되지 않으면 `02_generated_creatives` 시트의 `image_error` 컬럼을 확인합니다.
- 생성된 이미지는 `outputs/images` 폴더에서 확인합니다.

## 현재 운영 방식

현재는 `03_creative_review` 시트를 사용하지 않습니다.

운영 흐름은 아래와 같습니다.

```txt
01_campaign_brief
→ status = ready
→ 02_generated_creatives 생성
→ 02_generated_creatives에서 직접 확인
→ 마음에 드는 항목 status = approved
→ 이미지 자동 생성
→ outputs/images 저장
```

`03_creative_review` 시트는 향후 팀 검수, 법무 검수, 최종 승인본 관리, 광고 업로드 자동화 단계에서 사용할 수 있습니다.