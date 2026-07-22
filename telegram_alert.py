import time
import requests
import os
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from topaz_scraper import TopazScraper


BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

TARGET_ODD = float(
    os.getenv("TARGET_ODD", "5.00")
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

if not CHAT_ID:
    raise RuntimeError("CHAT_ID environment variable is missing")


sent_matches = set()


def telegram_send(text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=15
    )

    if response.status_code != 200:
        print(response.text)



def format_time(value):

    if value is None:
        return "Unknown"

    try:

        baku = timezone(
            timedelta(hours=4)
        )

        dt = datetime.fromtimestamp(
            int(value),
            tz=baku
        )

        return dt.strftime("%d.%m.%Y %H:%M")

    except Exception as e:

        print("TIME ERROR:", e)

        return "Unknown"


def check_odds(match):

    alerts = []

    home = float(match["odds"].get("101", 0))
    away = float(match["odds"].get("102", 0))

    first_half_draw = float(match["odds"].get("1001", 0))

    if home == TARGET_ODD:
        alerts.append(f"1️⃣ Ev {home:.2f}")

    if away == TARGET_ODD:
        alerts.append(f"2️⃣ Qonaq {away:.2f}")

    if first_half_draw in (2.29, 2.31):
        alerts.append(f"⏱️ 1-ci Hissə X {first_half_draw:.2f}")

    return alerts


def create_key(match):
    return match["id"]


def process_matches(matches):

    for match in matches:

        alerts = check_odds(match)

        if not alerts:
            continue

        key = create_key(match)

        if key in sent_matches:
            continue

        game_time = format_time(
            match.get("start_time")
        )

        message = f"""⚽️ TOPAZ ALERT

📅 {game_time}

🌍 {match['country']}
🏆 {match['tournament']}

⚔️ {match['home']} - {match['away']}

🎯 {' | '.join(alerts)}
"""

        telegram_send(message)

        print(
            "SENT:",
            match["home"],
            "-",
            match["away"]
        )

        sent_matches.add(key)


def scraper_job():

    print("\nChecking Topaz odds...")

    try:

        scraper = TopazScraper()

        data = scraper.get_events()

        matches = scraper.extract_1x2(data)

        print("Matches:", len(matches))

        process_matches(matches)

    except Exception as e:

        print("ERROR:", e)


scheduler = BackgroundScheduler()

scheduler.add_job(
    scraper_job,
    "interval",
    minutes=5
)

scheduler.start()

print("Telegram Topaz watcher started...")

# İlk dəfə dərhal işləsin
scraper_job()

try:

    while True:
        time.sleep(10)

except KeyboardInterrupt:

    scheduler.shutdown()
