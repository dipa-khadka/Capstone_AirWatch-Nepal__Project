"""

How it works: one call to aqicn.org lists every live station inside Nepal. For every city in the
LOCATION table we pick the nearest station (at most 25 km away, updated in the last 48 hours), read its
pollutant values and save one row in AQ_READING. Saving the same reading twice
is harmless, because the table has a unique key on (city, source, time).

Cities with no usable live station get a fallback: the current hourly values of the Open-Meteo computer
model (CAMS), saved under their own source name "Open-Meteo (CAMS model)". They are model estimates, not station
measurements, and the website says so. A city that has a live station never gets model rows.


The dashboard's "Update live data" button and the optional automatic refresh call collect_once() too.
"""
import math
import os
from datetime import datetime, timedelta, timezone
import sys
import time
import requests
from db import get_conn
from import_openmeteo import API as MODEL_API, SOURCE as MODEL_SOURCE, pm25_to_aqi

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
        except (KeyError, ValueError, TypeError):
            continue
        if nearest_km is None or km < nearest_km:
            nearest_km = km
        try:
            int(st["aqi"])                                          # "-" means no AQI right now
            age = now - station_time(st)
        except (KeyError, ValueError, TypeError):
            continue
        if km <= MAX_KM and age <= timedelta(hours=MAX_AGE_HOURS) and (best is None or km < best_km):
            best, best_km = st, km
    if best:
        return best, best_km, None
    if nearest_km is None or nearest_km > MAX_KM:
        return None, nearest_km, f"no live station within {MAX_KM} km"
    return None, nearest_km, "the nearby station has no current reading"


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


def model_fallback(cur, cities, now=None):
    """Cities without a live station: saves the last 7 days of Open-Meteo model values (hourly, up to the current
    hour) and returns one result per city. Only hours newer than the city's newest saved reading are added,
    so existing data is never touched and the same hour is never saved twice."""
    if not cities:
        return []
    now = (now or datetime.now(NEPAL_TZ)).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    try:  # one request for all these cities (Open-Meteo accepts a list of coordinates)
        r = requests.get(MODEL_API, timeout=60, params={
            "latitude": ",".join(str(float(c["latitude"])) for c in cities),
            "longitude": ",".join(str(float(c["longitude"])) for c in cities),
            "hourly": "pm2_5,pm10,ozone", "past_days": 7, "forecast_days": 1, "timezone": "Asia/Kathmandu"})
        r.raise_for_status()
        data = r.json()
        data = data if isinstance(data, list) else [data]
        if len(data) != len(cities):
            raise RuntimeError("unexpected answer from Open-Meteo")
    except Exception as e:
        return [{"city": c["city_name"], "ok": False, "error": f"no live station, and the model estimate failed ({e})"} for c in cities]
    cur.execute("INSERT IGNORE INTO data_source (source_name, source_url) VALUES (%s, %s)",
                (MODEL_SOURCE, "https://open-meteo.com/en/docs/air-quality-api"))
    cur.execute("SELECT source_id FROM data_source WHERE source_name = %s", (MODEL_SOURCE,))
    sid = cur.fetchone()["source_id"]
    out = []
    for c, d in zip(cities, data):
        try:
            h = d["hourly"]
            hours = [(datetime.fromisoformat(t), a, b, o) for t, a, b, o in zip(h["time"], h["pm2_5"], h["pm10"], h["ozone"])
                     if a is not None and datetime.fromisoformat(t) <= now]
            if not hours:
                raise RuntimeError("no values for this city")
            # A city that had a real station reading in the last 3 days keeps its station data: model values are
            # not mixed in, because they would distort the daily averages and the prediction.
            cur.execute("SELECT MAX(r.`timestamp`) AS last_station FROM aq_reading r JOIN data_source s ON s.source_id = r.source_id "
                        "WHERE r.location_id = %s AND s.source_name NOT LIKE 'Open-Meteo%%'", (c["location_id"],))
            last_station = cur.fetchone()["last_station"]
            if last_station is not None and now - last_station < timedelta(hours=72):
                out.append({"city": c["city_name"], "ok": False, "error": "no live station right now, the last station reading is kept (model values are not mixed in)"})
                continue
            cur.execute("SELECT MAX(`timestamp`) AS newest FROM aq_reading WHERE location_id = %s", (c["location_id"],))
            newest = cur.fetchone()["newest"]
            new = 0
            for t, pm25, pm10, o3 in hours:
                if newest is not None and t <= newest:
                    continue                                   # keep what is already saved, add only newer hours
                aqi = pm25_to_aqi(pm25)
                if aqi is None:
                    continue
                o3_ppb = round(o3 / 1.96, 2) if o3 is not None else None   # ug/m3 to ppb, same as import_openmeteo.py
                cur.execute("INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, aqi_value) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)", (c["location_id"], sid, t.strftime("%Y-%m-%d %H:%M:%S"), pm25, pm10, o3_ppb, aqi))
                new += cur.rowcount
            t, pm25 = hours[-1][0], hours[-1][1]
            out.append({"city": c["city_name"], "ok": True, "aqi": pm25_to_aqi(pm25), "time": t.strftime("%Y-%m-%d %H:%M:%S"),
                        "station": "model estimate, not a station", "model": True, "new": new})
        except Exception as e:
            out.append({"city": c["city_name"], "ok": False, "error": f"no live station, and the model estimate failed ({e})"})
    return out


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
            no_station = []              # cities that get the model fallback below
            for loc in cur.fetchall():
                city = loc["city_name"]
                try:
                    st, km, why = pick_station(loc["latitude"], loc["longitude"], stations)
                    if not st:
                        no_station.append(loc)
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
            results += model_fallback(cur, no_station)
            results.sort(key=lambda r: r["city"])
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