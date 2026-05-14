import time
import subprocess
from datetime import datetime

CHECK_INTERVAL = 5

print("===================================")
print("Creative Automation Watcher Started")
print("===================================")

while True:
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n[{now}] Checking Google Sheets...")

        subprocess.run(
            ["python", "scripts/generate_creatives_from_brief.py"],
            check=False
        )

        subprocess.run(
            ["python", "scripts/generate_images_from_creatives.py"],
            check=False
        )

        print(f"[{now}] Waiting {CHECK_INTERVAL} seconds...")

    except Exception as e:
        print("Watcher Error:", e)

    time.sleep(CHECK_INTERVAL)