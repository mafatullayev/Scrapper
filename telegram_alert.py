import os
import time
from datetime import datetime, timedelta, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from topaz_scraper import TopazScraper

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

TARGET_ODD = float(os.getenv("TARGET_ODD", "5.00"))
SMART_DRAW_ODD = float(os.getenv("SMART_DRAW_ODD", "1.85"))
SMART_BEFORE_MINUTES = int(os.getenv("SMART_BEFORE_MINUTES", "10"))
FULL_TIME_DRAW_ODD = 2.31

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

if not CHAT_ID:
    raise RuntimeError("CHAT_ID environment variable is missing")

if SMART_BEFORE_MINUTES <= 0:
    raise RuntimeError("SMART_BEFORE_MINUTES must be greater than 0")


target_sent_matches = set()

combo_sent_matches = set()

smart_sent_matches = set()

opening_first_half_draw = {}


def odds_equal(left, right):
    try:
        return round(float(left), 2) == round(float(right), 2)
    except (TypeError, ValueError):
        return False


def telegram_send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text
            },
            timeout=15
        )

        if response.status_code != 200:
            print(
                "TELEGRAM ERROR:",
                response.status_code,
                response.text
            )
            return False

        return True

    except requests.RequestException as error:
        print("TELEGRAM REQUEST ERROR:", error)
        return False


def timestamp_to_datetime(value, tz):
    timestamp = int(value)

    # Defensive support for millisecond timestamps.
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000

    return datetime.fromtimestamp(timestamp, tz=tz)


def format_time(value):
    if value is None:
        return "Unknown"

    try:
        baku_timezone = timezone(timedelta(hours=4))

        game_datetime = timestamp_to_datetime(
            value,
            baku_timezone
        )

        return game_datetime.strftime("%d.%m.%Y %H:%M")

    except (TypeError, ValueError, OSError) as error:
        print("TIME FORMAT ERROR:", error)
        return "Unknown"


def remaining_minutes_until_game(start_time):
    if start_time is None:
        return None

    try:
        game_start_utc = timestamp_to_datetime(
            start_time,
            timezone.utc
        )

        now_utc = datetime.now(timezone.utc)

        return (
            game_start_utc - now_utc
        ).total_seconds() / 60

    except (TypeError, ValueError, OSError) as error:
        print("REMAINING TIME ERROR:", error)
        return None

def get_normal_conditions(match):
    odds = match.get("odds", {})

    home = odds.get("101")
    draw = odds.get("100")
    away = odds.get("102")

    home_hit = odds_equal(home, TARGET_ODD)
    away_hit = odds_equal(away, TARGET_ODD)
    draw_hit = odds_equal(draw, FULL_TIME_DRAW_ODD)

    target_hit = home_hit or away_hit
    combo_hit = target_hit and draw_hit

    return {
        "home": home,
        "draw": draw,
        "away": away,
        "home_hit": home_hit,
        "away_hit": away_hit,
        "draw_hit": draw_hit,
        "target_hit": target_hit,
        "combo_hit": combo_hit,
    }


def build_target_alert(conditions):
    parts = []

    if conditions["home_hit"]:
        parts.append(
            f"1️⃣ Ev {float(conditions['home']):.2f}"
        )

    if conditions["away_hit"]:
        parts.append(
            f"2️⃣ Qonaq {float(conditions['away']):.2f}"
        )

    if not parts:
        return None

    return "🎯 TARGET: " + " | ".join(parts)


def build_combo_alert(conditions):
    target_parts = []

    if conditions["home_hit"]:
        target_parts.append(
            f"1️⃣ Ev {float(conditions['home']):.2f}"
        )

    if conditions["away_hit"]:
        target_parts.append(
            f"2️⃣ Qonaq {float(conditions['away']):.2f}"
        )

    if not target_parts or not conditions["draw_hit"]:
        return None

    return (
        "🔥 COMBO: "
        + " | ".join(target_parts)
        + f" + 🤝 FT X {float(conditions['draw']):.2f}"
    )

def register_opening_first_half_draw(match):

    match_id = match["id"]

    if match_id in opening_first_half_draw:
        return

    current_draw = match.get("odds", {}).get("1001")

    if current_draw is None:
        return

    try:
        current_draw = float(current_draw)
    except (TypeError, ValueError):
        return

    if current_draw <= 0:
        return

    opening_first_half_draw[match_id] = current_draw

    print(
        f"OPENING OBSERVED: {match['home']} - {match['away']} | "
        f"1H X={current_draw:.2f}"
    )


def get_smart_alert(match):

    match_id = match["id"]
    smart_key = f"{match_id}_SMART"

    if smart_key in smart_sent_matches:
        return None, None

    register_opening_first_half_draw(match)

    opening_draw = opening_first_half_draw.get(match_id)

    if opening_draw is None:
        return None, None

    current_draw = match.get("odds", {}).get("1001")

    if not odds_equal(opening_draw, SMART_DRAW_ODD):
        return None, None

    if not odds_equal(current_draw, SMART_DRAW_ODD):
        return None, None

    remaining = remaining_minutes_until_game(
        match.get("start_time")
    )

    if remaining is None:
        return None, None

    if remaining < 0:
        return None, None

    if remaining > SMART_BEFORE_MINUTES:
        return None, None

    print(
        f"SMART MATCH: {match['home']} - {match['away']} | "
        f"Opening={float(opening_draw):.2f} "
        f"Current={float(current_draw):.2f} "
        f"Remaining={remaining:.1f}m"
    )

    alert_text = (
        f"🧠 SMART: 1-ci hissə X {float(current_draw):.2f}\n"
        f"⌛ Oyuna təxminən {max(0, int(remaining))} dəqiqə qalıb"
    )

    return alert_text, smart_key

def process_matches(matches):
    for match in matches:
        match_id = match["id"]

        alerts = []
        keys_to_mark_after_success = []

        target_key = f"{match_id}_TARGET"
        combo_key = f"{match_id}_COMBO"

        conditions = get_normal_conditions(match)

        if (
            conditions["combo_hit"]
            and combo_key not in combo_sent_matches
        ):
            combo_alert = build_combo_alert(conditions)

            if combo_alert:
                alerts.append(combo_alert)
                keys_to_mark_after_success.append(
                    ("combo", combo_key)
                )

                if target_key not in target_sent_matches:
                    keys_to_mark_after_success.append(
                        ("target", target_key)
                    )

        elif (
            conditions["target_hit"]
            and target_key not in target_sent_matches
        ):
            target_alert = build_target_alert(conditions)

            if target_alert:
                alerts.append(target_alert)
                keys_to_mark_after_success.append(
                    ("target", target_key)
                )

        smart_alert, smart_key = get_smart_alert(match)

        if smart_alert:
            alerts.append(smart_alert)
            keys_to_mark_after_success.append(
                ("smart", smart_key)
            )

        if not alerts:
            continue

        game_time = format_time(
            match.get("start_time")
        )

        message = f"""⚽️ TOPAZ ALERT

📅 {game_time}

🌍 {match['country']}
🏆 {match['tournament']}

⚔️ {match['home']} - {match['away']}

{chr(10).join(alerts)}
"""

        if not telegram_send(message):
            continue

        for alert_type, key in keys_to_mark_after_success:

            if alert_type == "target":
                target_sent_matches.add(key)

            elif alert_type == "combo":
                combo_sent_matches.add(key)

            elif alert_type == "smart":
                smart_sent_matches.add(key)

        print(
            "SENT:",
            match_id,
            match["home"],
            "-",
            match["away"],
            "|",
            ", ".join(
                alert_type.upper()
                for alert_type, _ in keys_to_mark_after_success
            )
        )


def scraper_job():
    print("\nChecking Topaz odds...")

    try:
        scraper = TopazScraper()

        data = scraper.get_events()

        matches = scraper.extract_1x2(data)

        print("Matches:", len(matches))

        process_matches(matches)

    except Exception as error:
        print(
            "SCRAPER JOB ERROR:",
            type(error).__name__,
            error
        )


def main():
    scheduler = BackgroundScheduler(
        timezone="UTC"
    )

    scheduler.add_job(
        scraper_job,
        trigger="interval",
        minutes=3,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60
    )

    scheduler.start()

    print("Telegram Topaz watcher started...")

    scraper_job()

    try:
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
