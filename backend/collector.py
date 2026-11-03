"""Data collection (Sujit's part). Gets new readings from aqicn.org and saves them.

Run once:            python backend/collector.py
Run every 60 min:    python backend/collector.py --every 60
Needs WAQI_TOKEN in the .env file (free: https://aqicn.org/data-platform/token/).
"""
import os
import sys
import time
import requests
from db import get_conn

TOKEN = os.getenv("WAQI_TOKEN", "")
URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"
COLS = {"pm25": "pm25", "pm10": "pm10", "o3": "o3", "no2": "no2", "so2": "so2", "co": "co"}


def fetch(lat, lon):
    r = requests.get(URL.format(lat=lat, lon=lon), params={"token": TOKEN}, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "ok":
        raise RuntimeError(str(body.get("data")))
    return body["data"]


def collect_once():
    if not TOKEN:
        sys.exit("WAQI_TOKEN is empty. Put your token in the .env file.")
    conn = get_conn()
    saved = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT source_id FROM data_source WHERE source_name = 'aqicn.org'")
            source_id = cur.fetchone()["source_id"]
            cur.execute("SELECT location_id, city_name, latitude, longitude FROM location")
            for loc in cur.fetchall():
                try:
                    d = fetch(loc["latitude"], loc["longitude"])
                    if not isinstance(d.get("aqi"), int):
                        print(f"{loc['city_name']}: no AQI right now, skipped")
                        continue
                    iaqi = d.get("iaqi", {})
                    vals = [iaqi.get(k, {}).get("v") for k in COLS]
                    cur.execute(
                        "INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, no2, so2, co, aqi_value) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (loc["location_id"], source_id, d["time"]["s"], *vals, d["aqi"]))
                    saved += cur.rowcount
                    print(f"{loc['city_name']}: AQI {d['aqi']} at {d['time']['s']} (station: {d.get('city', {}).get('name', '?')})")
                except Exception as e:  # one city failing must not stop the others
                    print(f"{loc['city_name']}: failed ({e})")
    finally:
        conn.close()
    print(f"Saved {saved} new reading(s).")


if __name__ == "__main__":
    if "--every" in sys.argv:
        minutes = int(sys.argv[sys.argv.index("--every") + 1])
        while True:
            collect_once()
            time.sleep(minutes * 60)
    else:
        collect_once()
