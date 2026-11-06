"""Diagnostic tool: lists the air quality stations aqicn.org knows inside Nepal.

Run:  python backend/list_stations.py
It prints station id (uid), name, AQI and last update time. Nothing is saved.
We use it to find which Nepali stations really exist and are alive, because the
"nearest station" lookup used by the collector returns stations in Tibet and India.
"""
import requests
import collector  # reads WAQI_TOKEN from the .env file

BOX = "26.3,80.0,30.5,88.3"  # south, west, north, east: a box around Nepal
KEYWORDS = ["nepal", "kathmandu", "pokhara", "biratnagar", "lalitpur", "bhaktapur", "chitwan", "janakpur", "birgunj", "butwal"]


def get(path, **params):
    """Calls the aqicn API and returns the list in 'data' (or an empty list)."""
    r = requests.get("https://api.waqi.info/" + path, params={"token": collector.TOKEN, **params}, timeout=20)
    body = r.json()
    return body.get("data") if body.get("status") == "ok" and isinstance(body.get("data"), list) else []


print("1) Stations inside the Nepal box")
for s in get("v2/map/bounds", latlng=BOX):
    st = s.get("station", {})
    print(f"  uid {s.get('uid'):>6}  AQI {str(s.get('aqi')):>4}  {st.get('time', '')[:16]}  {st.get('name')}  ({s.get('lat')}, {s.get('lon')})")

print("\n2) Search by keyword")
seen = set()
for k in KEYWORDS:
    for s in get("search/", keyword=k):
        uid = s.get("uid")
        name = s.get("station", {}).get("name", "")
        if uid in seen or "nepal" not in name.lower() and "nepal" not in s.get("station", {}).get("url", "").lower():
            continue
        seen.add(uid)
        print(f"  uid {uid:>6}  AQI {str(s.get('aqi')):>4}  {s.get('time', {}).get('stime', '')}  {name}")