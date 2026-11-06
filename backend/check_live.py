"""Diagnostic tool: shows what aqicn.org returns for every city, so we can see why a city has no live data.

Run:  python backend/check_live.py
It does not save anything. For each city it prints the nearest station, its distance and its last update time.
"""
from dotenv import load_dotenv
load_dotenv()  # reads WAQI_TOKEN from the .env file
import collector
from db import get_conn

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT city_name, latitude, longitude FROM location ORDER BY city_name")
rows = cur.fetchall()
conn.close()

print("Token set:", bool(collector.TOKEN))
for r in rows:
    city, lat, lon = (r["city_name"], float(r["latitude"]), float(r["longitude"])) if isinstance(r, dict) else (r[0], float(r[1]), float(r[2]))
    try:
        d = collector.fetch(lat, lon)
        geo = d.get("city", {}).get("geo") or [lat, lon]
        km = collector.km_between(lat, lon, geo[0], geo[1])
        print(f"{city:11} {km:6.0f} km  AQI {d.get('aqi')}  {d.get('time', {}).get('s')}  {d.get('city', {}).get('name')}")
    except Exception as e:
        print(f"{city:11} ERROR {e}")