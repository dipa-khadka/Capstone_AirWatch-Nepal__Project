"""Fills the 2022 to 2025 gap of every city with modelled air quality data from Open-Meteo (free, no key).

IMPORTANT: this is NOT a station measurement. Open-Meteo gives computer model estimates
(CAMS, Copernicus Atmosphere Monitoring Service). The numbers can differ from the US Embassy station,
so the data is saved under its own source name and shown as such on the History page.

Run it (the .env file decides which database is used, local or cloud):
  python backend/import_openmeteo.py
  python backend/import_openmeteo.py --city Kathmandu     (only one city; the default is all cities)
Open-Meteo has data from about August 2022, so earlier days come back empty.
Add --dry to only download and count, without saving.
"""
import argparse
from datetime import date, timedelta

import time

import requests

from db import get_conn

API = "https://air-quality-api.open-meteo.com/v1/air-quality"
SOURCE = "Open-Meteo (CAMS model)"


def pm25_to_aqi(c):
    """US EPA AQI from a PM2.5 value in ug/m3 (same table as import_csv.py)."""
    table = [(0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), (55.5, 150.4, 151, 200),
             (150.5, 250.4, 201, 300), (250.5, 350.4, 301, 400), (350.5, 500.4, 401, 500)]
    c = int(c * 10) / 10
    for lo, hi, a, b in table:
        if lo <= c <= hi:
            return round((b - a) / (hi - lo) * (c - lo) + a)
    return 500 if c > 500.4 else None


def download(lat, lon, start, end):
    """Hourly PM2.5, PM10 and ozone between two dates. Returns a list of (time, pm25, pm10, o3_ug)."""
    r = requests.get(API, timeout=60, params={
        "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
        "hourly": "pm2_5,pm10,ozone", "timezone": "Asia/Kathmandu"})
    r.raise_for_status()
    h = r.json()["hourly"]
    return list(zip(h["time"], h["pm2_5"], h["pm10"], h["ozone"]))


def save(conn, city, rows):
    """Saves the hourly rows of one city. INSERT IGNORE skips readings that are already there."""
    with conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO data_source (source_name, source_url) VALUES (%s, %s)",
                    (SOURCE, "https://open-meteo.com/en/docs/air-quality-api"))
        cur.execute("SELECT source_id FROM data_source WHERE source_name = %s", (SOURCE,))
        sid = cur.fetchone()["source_id"]
        batch = []
        for t, pm25, pm10, o3 in rows:
            aqi = pm25_to_aqi(pm25)
            if aqi is None:
                continue
            o3_ppb = round(o3 / 1.96, 2) if o3 is not None else None   # ug/m3 to ppb (ozone, about 25 C)
            batch.append((city["location_id"], sid, t.replace("T", " "), pm25, pm10, o3_ppb, aqi))
        saved = 0
        for i in range(0, len(batch), 1000):
            cur.executemany("INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, aqi_value) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)", batch[i:i + 1000])
            saved += cur.rowcount
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", default="all", help="one city name, or all (default)")
    ap.add_argument("--from", dest="start", default="2022-08-01", help="first day (Open-Meteo has nothing before about 2022-08)")
    ap.add_argument("--to", dest="end", default="2025-12-31")
    ap.add_argument("--dry", action="store_true", help="only download and count, do not save")
    a = ap.parse_args()

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT location_id, city_name, latitude, longitude FROM location ORDER BY city_name")
        cities = [c for c in cur.fetchall() if a.city.lower() in ("all", c["city_name"].lower())]
    if not cities:
        raise SystemExit("No city with that name.")

    for c in cities:
        # Ask for one year at a time, so a failed request only loses one year
        rows, day, last = [], date.fromisoformat(a.start), date.fromisoformat(a.end)
        while day <= last:
            stop = min(day + timedelta(days=364), last)
            try:
                got = download(float(c["latitude"]), float(c["longitude"]), day.isoformat(), stop.isoformat())
            except Exception as e:  # keep going with the next year
                print(f"  {c['city_name']} {day} to {stop}: failed ({e})")
                got = []
            rows += [g for g in got if g[1] is not None]
            day = stop + timedelta(days=1)
            time.sleep(1)   # be gentle with the free service
        saved = 0 if a.dry else save(conn, c, rows)
        print(f"{c['city_name']}: {len(rows)} hourly values downloaded" + ("" if a.dry else f", {saved} saved"))
    conn.close()


if __name__ == "__main__":
    main()
