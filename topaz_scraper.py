import requests
import time


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


    def get_events(self):

        now = int(time.time() * 1000)


        params = {

            "sortId": 1,

            "live": "false",

            "pageOffset": 0,

            "pageLimit": 500,

            "sportTypeId": "1:sr:sport:1",

            "startDate": now,

            "endDate": now + (48 * 60 * 60 * 1000)

        }


        response = requests.get(
            self.url,
            headers=self.headers,
            params=params,
            timeout=30
        )


        print("STATUS:", response.status_code)


        response.raise_for_status()


        return response.json()



    def extract_1x2(self, data):


        matches = []


        for season in data["item"]["seasons"]:


            country = season.get("categoryName")

            tournament = season.get("seasonName")


            for event in season.get("events", []):


                home = event["teams"]["home"]["aze"]

                away = event["teams"]["away"]["aze"]



                start_time = (

                    event.get("startTime")
                    or
                    event.get("startDate")
                    or
                    event.get("date")
                    or
                    event.get("scheduled")
                )



                markets = event.get("markets", [])

                match = {
                    "id": event["id"],
                    "country": country,
                    "tournament": tournament,
                    "home": home,
                    "away": away,
                    "start_time": event.get("startedAt"),
                    "odds": {}
                }

                for market in markets:

                    # Tam oyun 1X2
                    if market.get("marketRefId") == "1:1":

                        for outcome in market.get("outcomes", []):
                            code = str(outcome.get("shortCode"))
                            odd = outcome.get("odd")

                            match["odds"][code] = odd

                    # 1-ci hissə 1X2
                    elif market.get("marketRefId") == "1:60":

                        for outcome in market.get("outcomes", []):
                            code = str(outcome.get("shortCode"))
                            odd = outcome.get("odd")

                            match["odds"][code] = odd

                matches.append(match)



        return matches
