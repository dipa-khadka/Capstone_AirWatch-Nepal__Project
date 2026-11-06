"""Data collection (Sujit's part). Gets new readings from aqicn.org and saves them in the database.

How it works: one call to aqicn.org lists every live station inside Nepal. For every city in the
LOCATION table we pick the nearest station (at most 25 km away, updated in the last 48 hours), read its
pollutant values and save one row in AQ_READING. Saving the same reading twice
is harmless, because the table has a unique key on (city, source, time).

Run once:            python backend/collector.py
Run every 60 min:    python backend/collector.py --every 60
Needs WAQI_TOKEN in the .env file (free: https://aqicn.org/data-platform/token/).
The dashboard's "Update live data" button and the optional automatic refresh call collect_once() too.
"""
import math
import os
from datetime import datetime, timedelta, timezone
import sys
import time
import requests
from db import get_conn

TOKEN = os.getenv("WAQI_TOKEN", "")  # your free aqicn.org token, kept in the .env file
URL = "https://api.waqi.info/feed/geo:{lat};{lon}/"  # "give me the nearest station to this point"
COLS = ["pm25", "pm10", "o3", "no2", "so2", "co"]  # the pollutants we store
MAP_URL = "https://api.waqi.info/v2/map/bounds"  # "list all stations inside this box"
NEPAL_BOX = "26.3,80.0,30.5,88.3"  # south, west, north, east: a box around Nepal
MAX_AGE_HOURS = 48  # a station that has not updated for this long is treated as offline
NEPAL_TZ = timezone(timedelta(hours=5, minutes=45))  # Nepal time, used when a station gives its time in UTC
MAX_KM = 25  # the feed gives the nearest station; a station farther than this does not describe the city


def km_between(lat1, lon1, lat2, lon2):
    """Distance in kilometres between two points on the earth (haversine formula)."""
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def fetch(lat, lon):
    """Asks aqicn.org for the nearest station's data. Returns the 'data' part of the answer."""
    r = requests.get(URL.format(lat=lat, lon=lon), params={"token": TOKEN}, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "ok":
        raise RuntimeError(str(body.get("data")))
    return body["data"]


def nepal_stations():
    """One call that returns every station aqicn.org has inside Nepal (id, position, AQI, last update)."""
    r = requests.get(MAP_URL, params={"token": TOKEN, "latlng": NEPAL_BOX}, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "ok":
        raise RuntimeError(str(body.get("data")))
    return body["data"]


def station_time(st):
    """Reads a station's update time as a timezone-aware datetime (UTC if the text has no zone)."""
    t = datetime.fromisoformat(st["station"]["time"].replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def pick_station(lat, lon, stations, now=None):
    """Chooses the nearest live station for a city.
    Returns (station, km, None) when one is good enough, or (None, km_or_None, reason) when not."""
    now = now or datetime.now(timezone.utc)
    best, best_km, nearest_km = None, None, None
    for st in stations:
        try:
            km = km_between(float(lat), float(lon), float(st["lat"]), float(st["lon"]))
            int(st["aqi"])                                          # "-" means no AQI right now
            age = now - station_time(st)
        except (KeyError, ValueError, TypeError):
            continue
        if nearest_km is None or km < nearest_km:
            nearest_km = km
        if km <= MAX_KM and age <= timedelta(hours=MAX_AGE_HOURS) and (best is None or km < best_km):
            best, best_km = st, km
    if best:
        return best, best_km, None
    if nearest_km is None or nearest_km > MAX_KM:
        return None, nearest_km, f"no live station within {MAX_KM} km"
    return None, nearest_km, "the nearby station has not updated recently"


def read_station(st):
    """Gets the pollutant values of one station. Returns (aqi, time text, pollutant list).
    If the detailed feed is not available we still save the AQI that the station list gave us."""
    try:
        r = requests.get(f"https://api.waqi.info/feed/@{st['uid']}/", params={"token": TOKEN}, timeout=15)
        body = r.json()
        if body.get("status") == "ok" and isinstance(body["data"].get("aqi"), int):
            d = body["data"]
            return d["aqi"], d["time"]["s"], [d.get("iaqi", {}).get(k, {}).get("v") for k in COLS]
    except Exception:
        pass  # fall back to the station list values below
    when = station_time(st).astimezone(NEPAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return int(st["aqi"]), when, [None] * len(COLS)


def collect_once():
    """Fetch one reading for every city and save it. Returns one result per city."""
    if not TOKEN:
        raise RuntimeError("WAQI_TOKEN is empty. Put your token in the .env file and restart the server.")
    results = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT source_id FROM data_source WHERE source_name = 'aqicn.org'")
            source_id = cur.fetchone()["source_id"]
            cur.execute("SELECT location_id, city_name, latitude, longitude FROM location ORDER BY city_name")
            stations = nepal_stations()  # one call for all cities
            for loc in cur.fetchall():
                city = loc["city_name"]
                try:
                    st, km, why = pick_station(loc["latitude"], loc["longitude"], stations)
                    if not st:
                        extra = f" (nearest is {km:.0f} km away)" if km is not None else ""
                        results.append({"city": city, "ok": False, "error": f"{why}{extra}, skipped"})
                        continue
                    aqi, when, vals = read_station(st)
                    cur.execute(
                        "INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, no2, so2, co, aqi_value) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (loc["location_id"], source_id, when, *vals, aqi))
                    results.append({"city": city, "ok": True, "aqi": aqi, "time": when,
                                    "station": f"{st['station']['name']}, {km:.0f} km", "new": cur.rowcount})
                except Exception as e:  # one city failing must not stop the others
                    results.append({"city": city, "ok": False, "error": str(e)})
    finally:
        conn.close()
    return results


def print_results(results):
    """Prints one line per city, for people who run the script in a terminal."""
    for r in results:
        if r["ok"]:
            print(f"{r['city']}: AQI {r['aqi']} at {r['time']} (station: {r['station']})")
        else:
            print(f"{r['city']}: failed ({r['error']})")
    print(f"Saved {sum(r.get('new', 0) for r in results)} new reading(s).")


if __name__ == "__main__":
    try:
        if "--every" in sys.argv:
            minutes = int(sys.argv[sys.argv.index("--every") + 1])
            while True:
                print_results(collect_once())
                time.sleep(minutes * 60)
        else:
            print_results(collect_once())
    except RuntimeError as e:
        sys.exit(str(e))