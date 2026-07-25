import time

import requests


class TopazScraper:

    def __init__(self):
        self.url = "https://tps.topaz.net.az/api/terminal/events"

        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "az",
            "mobile-auth": "29e0ef66-9809-4e0f-b6a7-fda09326501a",
            "origin": "https://topaz.az",
            "referer": "https://topaz.az/",
            "user-agent": "Mozilla/5.0",
            "x-lang": "aze",
            "x-mac-address": "63:14:9b:b2:65:cf"
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)


    def get_events(self):
        now_ms = int(time.time() * 1000)

        params = {
            "sortId": 1,
            "live": "false",
            "pageOffset": 0,
            "pageLimit": 500,
            "sportTypeId": "1:sr:sport:1",
            "startDate": now_ms,
            "endDate": now_ms + (24 * 60 * 60 * 1000)
        }

        response = self.session.get(
            self.url,
            params=params,
            timeout=30
        )

        print("STATUS:", response.status_code)

        response.raise_for_status()

        data = response.json()

        if not data.get("info", {}).get("success", False):
            raise RuntimeError(
                f"Topaz API returned unsuccessful response: "
                f"{data.get('info')}"
            )

        return data


    def extract_1x2(self, data):
        matches = []

        seasons = (
            data.get("item", {}).get("seasons", [])
            or []
        )

        for season in seasons:
            country = season.get("categoryName", "Unknown")
            tournament = season.get("seasonName", "Unknown")

            events = season.get("events", []) or []

            for event in events:
                event_id = event.get("id")

                if not event_id:
                    continue

                teams = event.get("teams", {}) or {}
                home_names = teams.get("home", {}) or {}
                away_names = teams.get("away", {}) or {}

                home = (
                    home_names.get("aze")
                    or home_names.get("eng")
                    or "Unknown home team"
                )

                away = (
                    away_names.get("aze")
                    or away_names.get("eng")
                    or "Unknown away team"
                )

                match = {
                    "id": event_id,
                    "country": country,
                    "tournament": tournament,
                    "home": home,
                    "away": away,
                    "start_time": (
                        event.get("startedAt")
                        or event.get("startTime")
                        or event.get("startDate")
                        or event.get("date")
                        or event.get("scheduled")
                    ),
                    "odds": {}
                }

                markets = event.get("markets", []) or []

                for market in markets:
                    market_ref_id = market.get("marketRefId")

                    if market_ref_id not in {"1:1", "1:60"}:
                        continue

                    outcomes = market.get("outcomes") or []

                    for outcome in outcomes:
                        short_code = outcome.get("shortCode")
                        odd = outcome.get("odd")

                        if short_code is None or odd is None:
                            continue

                        match["odds"][str(short_code)] = odd

                if match["odds"]:
                    matches.append(match)

        return matches