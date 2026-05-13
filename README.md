# Creative Automation

Google Sheets 기반 광고 크리에이티브 자동화 프로젝트입니다.

이 프로젝트는 Google Sheets에 입력된 캠페인 브리프를 기반으로 광고 카피, 이미지 프롬프트, 영상 프롬프트 등을 생성하고 관리하기 위한 자동화 템플릿입니다.

## 포함된 폴더 구조

```text
creative-automation-public/
├─ reference_images/
│  ├─ CABAL_MOBILE_JP/
│  ├─ CABAL_ONLINE_KR/
│  └─ CAT_CAFE_KR/
├─ scripts/
│  ├─ create_ad_creative_google_sheet_template.py
│  ├─ generate_creatives_from_brief.py
│  ├─ generate_images_from_creatives.py
│  └─ queue_creatives_for_review.py
├─ .env.example
├─ .gitignore
├─ README.md
└─ requirements.txt
```

## 필요한 API

이 프로젝트를 사용하려면 아래 API 또는 서비스 설정이 필요합니다.

### 1. Google Sheets API

Google Spreadsheet를 자동으로 읽고 쓰기 위해 필요합니다.

사용 예시:

- 캠페인 브리프 시트 생성
- 게임 데이터베이스 시트 생성
- 생성된 광고 카피 및 프롬프트 결과 입력
- 검수 상태 업데이트

### 2. Google Drive API

Google Spreadsheet 파일 접근 또는 생성 권한이 필요한 경우 사용될 수 있습니다.

### 3. Gemini API

광고 카피, 이미지 프롬프트, 영상 프롬프트 또는 이미지 생성 자동화를 위해 사용할 수 있습니다.

사용하지 않을 경우, 관련 코드 또는 환경변수 설정은 제외해도 됩니다.

## Google Sheets 연결법

### 1. Google Cloud 프로젝트 생성

Google Cloud Console에서 새 프로젝트를 생성합니다.

### 2. API 활성화

아래 API를 활성화합니다.

- Google Sheets API
- Google Drive API

### 3. 서비스 계정 생성

Google Cloud Console에서 서비스 계정을 생성합니다.

### 4. 서비스 계정 JSON 키 다운로드

서비스 계정의 JSON 키 파일을 다운로드합니다.

주의: 이 JSON 파일은 절대 GitHub에 업로드하면 안 됩니다.

### 5. Google Spreadsheet 공유

다운로드한 서비스 계정 JSON 파일 안에 있는 `client_email` 값을 확인합니다.

예시:

```text
example-service-account@project-id.iam.gserviceaccount.com
```

Google Spreadsheet 오른쪽 상단의 공유 버튼을 누르고, 위 이메일을 편집자 권한으로 추가합니다.

### 6. .env 파일 생성

`.env.example` 파일을 복사해서 `.env` 파일을 만듭니다.

예시:

```env
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account.json
```

`GOOGLE_SPREADSHEET_ID`는 Google Sheets 주소에서 확인할 수 있습니다.

예시 주소:

```text
https://docs.google.com/spreadsheets/d/여기가_스프레드시트_ID/edit
```

## 설치 방법

Python이 설치된 상태에서 아래 명령어를 실행합니다.

```bash
pip install -r requirements.txt
```

## 실행 순서

### 1. Google Sheets 템플릿 생성

```bash
python scripts/create_ad_creative_google_sheet_template.py
```

이 스크립트는 자동화에 필요한 Google Sheets 기본 구조를 생성합니다.

예상 시트 예시:

- 00_game_database
- 01_campaign_brief
- 02_generated_creatives

### 2. 캠페인 브리프 입력

Google Sheets의 `01_campaign_brief` 시트에 캠페인 정보를 입력합니다.

예시 입력 항목:

- game_code
- campaign_name
- campaign_goal
- country
- language
- media
- platform
- target_audience
- user_segment
- creative_type
- tone
- creative_angle
- promotion
- landing_url

### 3. 광고 크리에이티브 생성

```bash
python scripts/generate_creatives_from_brief.py
```

입력된 브리프를 기반으로 광고 카피, 이미지 프롬프트, 영상 프롬프트 등을 생성합니다.

생성 결과는 `02_generated_creatives` 시트에 기록됩니다.

### 4. 검수 대기열 생성

```bash
python scripts/queue_creatives_for_review.py
```

생성된 소재를 검수 가능한 상태로 정리합니다.

### 5. 이미지 생성

```bash
python scripts/generate_images_from_creatives.py
```

검수 완료된 프롬프트를 기반으로 이미지 생성을 실행합니다.

## 샘플 워크플로우

1. `00_game_database` 시트에 게임 기본 정보를 입력합니다.
2. `01_campaign_brief` 시트에 광고 캠페인 정보를 입력합니다.
3. `generate_creatives_from_brief.py`를 실행합니다.
4. `02_generated_creatives` 시트에서 생성된 카피와 프롬프트를 확인합니다.
5. 필요한 경우 사람이 직접 수정합니다.
6. 검수 상태를 `approved`로 변경합니다.
7. `generate_images_from_creatives.py`를 실행합니다.
8. 생성된 이미지를 확인하고 광고 소재로 활용합니다.

## 보안 주의사항

아래 파일은 절대 GitHub에 업로드하지 마세요.

```text
.env
credentials/
service-account.json
API key
logs/
outputs/
```

이 프로젝트에는 `.gitignore`가 포함되어 있어 위 파일들이 GitHub에 올라가지 않도록 설정되어 있습니다.

## 라이선스

이 프로젝트는 MIT License를 기준으로 배포할 수 있습니다.
