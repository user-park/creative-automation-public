@echo off
chcp 65001 > nul
echo [2단계] 승인된 approved 항목만 이미지로 생성합니다.
echo.
python scripts/generate_images_from_creatives.py
echo.
echo 완료되었습니다.
echo 생성된 이미지는 outputs 폴더에서 확인하세요.
echo.
pause