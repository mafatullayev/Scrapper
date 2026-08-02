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

        one_day_ms = 24 * 60 * 60 * 1000

        all_responses = []

        for window_index in range(3):

            start_date = now_ms + (
                    window_index * one_day_ms
            )

            end_date = now_ms + (
                    (window_index + 1) * one_day_ms
            )

            params = {
                "sortId": 1,
                "live": "false",
                "pageOffset": 0,
                "pageLimit": 500,
                "sportTypeId": "1:sr:sport:1",
                "startDate": start_date,
                "endDate": end_date
            }

            response = self.session.get(
                self.url,
                params=params,
                timeout=30
            )

            print(
                f"WINDOW {window_index + 1}/3 "
                f"STATUS: {response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            seasons = (
                    data.get("item", {}).get("seasons", [])
                    or []
            )

            raw_event_count = sum(
                len(season.get("events", []) or [])
                for season in seasons
            )

            print(
                f"WINDOW {window_index + 1}/3 "
                f"STATUS: {response.status_code} "
                f"RAW EVENTS: {raw_event_count}"
            )

            if not data.get("info", {}).get(
                    "success",
                    False
            ):
                raise RuntimeError(
                    "Topaz API returned unsuccessful "
                    f"response: {data.get('info')}"
                )

            all_responses.append(data)

        return all_responses

    def extract_1x2(self, data):

        matches_by_id = {}

        responses = (
            data
            if isinstance(data, list)
            else [data]
        )

        for response_data in responses:

            seasons = (
                    response_data
                    .get("item", {})
                    .get("seasons", [])
                    or []
            )

            for season in seasons:

                country = season.get(
                    "categoryName",
                    "Unknown"
                )

                tournament = season.get(
                    "seasonName",
                    "Unknown"
                )

                events = (
                        season.get("events", [])
                        or []
                )

                for event in events:

                    event_id = event.get("id")

                    if not event_id:
                        continue

                    teams = (
                            event.get("teams", {})
                            or {}
                    )

                    home_names = (
                            teams.get("home", {})
                            or {}
                    )

                    away_names = (
                            teams.get("away", {})
                            or {}
                    )

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

                    if event_id not in matches_by_id:
                        matches_by_id[event_id] = {
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

                    match = matches_by_id[event_id]

                    markets = (
                            event.get("markets", [])
                            or []
                    )

                    for market in markets:

                        market_ref_id = market.get(
                            "marketRefId"
                        )

                        if market_ref_id not in {
                            "1:1",
                            "1:60"
                        }:
                            continue

                        outcomes = (
                                market.get("outcomes")
                                or []
                        )

                        for outcome in outcomes:

                            short_code = outcome.get(
                                "shortCode"
                            )

                            odd = outcome.get("odd")

                            if (
                                    short_code is None
                                    or odd is None
                            ):
                                continue

                            match["odds"][
                                str(short_code)
                            ] = odd

        matches = [
            match
            for match in matches_by_id.values()
            if match["odds"]
        ]

        print(
            "UNIQUE EVENTS:",
            len(matches_by_id)
        )

        print(
            "MATCHES WITH RELEVANT ODDS:",
            len(matches)
        )

        return matches