"""Fills the database with SAMPLE readings so the app can be demonstrated without a token.
These are made-up numbers. Run:  python backend/sample_data.py
Remove them later with:          python backend/sample_data.py --clear
"""
import math
import random
import sys
from datetime import datetime, timedelta
from db import get_conn

# Typical AQI of each city in the made-up data (any city not listed uses 90)
BASE = {"Kathmandu": 150, "Pokhara": 70, "Bhaktapur": 120, "Lalitpur": 135, "Bharatpur": 95, "Biratnagar": 140,
        "Janakpur": 130, "Nepalgunj": 125, "Dhangadhi": 110, "Lumbini": 105}  # any other city uses 90


def main():
    """Adds 30 days of made-up readings (one every 6 hours) for every city, or removes them with --clear."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO data_source (source_name, source_url) VALUES ('Sample data', 'local')")
        cur.execute("SELECT source_id FROM data_source WHERE source_name = 'Sample data'")
        sid = cur.fetchone()["source_id"]
        if "--clear" in sys.argv:
            cur.execute("DELETE FROM aq_reading WHERE source_id = %s", (sid,))
            print("Sample readings removed.")
            return
        cur.execute("SELECT location_id, city_name FROM location")
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        n = 0
        for loc in cur.fetchall():
            rnd = random.Random(loc["city_name"])
            for h in range(30 * 24, -1, -6):  # one reading every 6 hours for 30 days
                t = now - timedelta(hours=h)
                # a slow wave plus a little random noise, kept between 15 and 320
                aqi = round(max(15, min(320, BASE.get(loc["city_name"], 90) + 28 * math.sin(h / 24 / 4.5) + (rnd.random() - .5) * 36)))
                cur.execute(
                    "INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, no2, so2, co, aqi_value) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (loc["location_id"], sid, t, round(aqi * .45, 1), round(aqi * .7, 1), round(15 + aqi * .15, 1),
                     round(10 + aqi * .12, 1), round(3 + aqi * .04, 1), round(.3 + aqi * .004, 2), aqi))
                n += cur.rowcount
        print(f"Added {n} sample readings.")


if __name__ == "__main__":
    main()
