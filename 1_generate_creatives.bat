@echo off
chcp 65001 > nul
echo [1단계] 01_campaign_brief 시트의 ready 항목을 기준으로 광고 카피와 프롬프트를 생성합니다.
echo.
python scripts/generate_creatives_from_brief.py
echo.
echo 완료되었습니다.
echo Google Sheets의 02_generated_creatives 시트와 03_creative_review 시트에서 결과를 확인하세요.
echo 수정이 필요하면 review_comment에 의견을 입력하거나, 승인할 항목은 review_status를 approved로 변경하세요.
echo.
pause