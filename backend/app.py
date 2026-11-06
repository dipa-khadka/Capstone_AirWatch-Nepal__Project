"""AirWatch Nepal backend: a small Flask web server.

It does two jobs:
  1. It serves the web page (the files in the frontend folder).
  2. It answers the page's questions with data from the MySQL database (the /api/... addresses).

Run it with:  python backend/app.py   (then open http://127.0.0.1:5001)

Main parts of this file:
  - helper functions that read the database
  - one function for each API address (each address belongs to one page or use case)
  - the live data refresh (button and optional automatic refresh)
"""
import os
import threading
import time
from datetime import date, datetime, timedelta

import pymysql
from flask import Flask, jsonify, request, send_from_directory

from db import query                           # runs a SQL question and returns the rows
from analysis import trend_stats, predict_next  # trend numbers and the 2-day estimate
from collector import collect_once             # fetches live readings from aqicn.org

# The website files (index.html, style.css, app.js, logo.svg) live in the frontend folder.
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=FRONTEND, static_url_path="")

# Database column name -> the name shown to users
POLLUTANTS = {"pm25": "PM2.5", "pm10": "PM10", "o3": "O3", "no2": "NO2", "so2": "SO2", "co": "CO"}


def error(msg, code=400):
    """Sends an error message to the page as JSON, for example {"error": "No readings yet"}."""
    return jsonify({"error": msg}), code


@app.errorhandler(pymysql.err.OperationalError)
def database_down(_):
    """If MySQL is not running or the password is wrong, show a clear message instead of a crash."""
    return error("Cannot reach the database. Check that MySQL is running and the .env settings are correct.", 503)


# ---------------------------------------------------------------------------
# Helper functions that read the database
# ---------------------------------------------------------------------------

def category(aqi):
    """Finds the health level (label and message) for an AQI number, using the HEALTH_CATEGORY table."""
    rows = query("SELECT label, message FROM health_category WHERE %s BETWEEN aqi_min AND aqi_max", (aqi,))
    return rows[0] if rows else {"label": "Unknown", "message": ""}


def latest_reading(city):
    """The newest reading of a city (with the city name and the data source name joined in)."""
    rows = query(
        "SELECT r.*, l.city_name, s.source_name FROM aq_reading r "
        "JOIN location l ON l.location_id = r.location_id JOIN data_source s ON s.source_id = r.source_id "
        "WHERE l.city_name = %s ORDER BY r.`timestamp` DESC LIMIT 1", (city,))
    return rows[0] if rows else None


def current_payload(city):
    """Everything the Home page needs about a city's newest reading, or None if the city has no data."""
    r = latest_reading(city)
    if not r:
        return None
    cat = category(r["aqi_value"])
    return {
        "city": city,
        "aqi": r["aqi_value"],
        "label": cat["label"],
        "message": cat["message"],
        "time": r["timestamp"].strftime("%Y-%m-%d %H:%M"),
        # "stale" means the newest reading is more than 24 hours old (Use Case UC-02, alternative flow)
        "stale": datetime.now() - r["timestamp"] > timedelta(hours=24),
        "source": r["source_name"],
        "pollutants": {name: (float(r[col]) if r[col] is not None else None) for col, name in POLLUTANTS.items()},
    }


def daily_series(city, days):
    """Daily average AQI for the last `days` days, counted back from the newest reading of that city.
    (Counting from the newest reading means old data still shows when there is nothing newer.)"""
    newest = query(
        "SELECT DATE(MAX(r.`timestamp`)) AS d FROM aq_reading r "
        "JOIN location l ON l.location_id = r.location_id WHERE l.city_name = %s", (city,))
    if not newest or newest[0]["d"] is None:
        return []
    since = newest[0]["d"] - timedelta(days=days - 1)
    return query(
        "SELECT DATE(r.`timestamp`) AS day, ROUND(AVG(r.aqi_value)) AS aqi "
        "FROM aq_reading r JOIN location l ON l.location_id = r.location_id "
        "WHERE l.city_name = %s AND r.`timestamp` >= %s GROUP BY DATE(r.`timestamp`) ORDER BY day",
        (city, since))


def range_series(city, start, end):
    """Daily average AQI between two dates (both days included). Used by the custom date range on Trends."""
    return query(
        "SELECT DATE(r.`timestamp`) AS day, ROUND(AVG(r.aqi_value)) AS aqi "
        "FROM aq_reading r JOIN location l ON l.location_id = r.location_id "
        "WHERE l.city_name = %s AND r.`timestamp` >= %s AND r.`timestamp` < %s "
        "GROUP BY DATE(r.`timestamp`) ORDER BY day",
        (city, start, end + timedelta(days=1)))


# ---------------------------------------------------------------------------
# API addresses (one per page or use case)
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Opens the website."""
    return send_from_directory(FRONTEND, "index.html")


@app.route("/api/cities")
def cities():
    """List of cities for the menus. Only cities that already have readings are listed,
    so a menu never offers an empty city."""
    rows = query("SELECT location_id AS id, city_name AS name, district FROM location l "
                 "WHERE EXISTS (SELECT 1 FROM aq_reading r WHERE r.location_id = l.location_id) ORDER BY city_name")
    if not rows:  # empty database: list every city so the page can still start
        rows = query("SELECT location_id AS id, city_name AS name, district FROM location ORDER BY city_name")
    return jsonify(rows)


@app.route("/api/current")
def current():
    """Home page (UC-02, UC-06, FR-02, FR-07): the newest reading, its health level and message."""
    city = request.args.get("city", "Kathmandu")
    data = current_payload(city)
    return jsonify(data) if data else error(f"No readings yet for {city}.", 404)


@app.route("/api/overview")
def overview():
    """'Air across Nepal' tiles on the Home page: the newest AQI of every city that has data."""
    out = []
    for c in query("SELECT city_name FROM location ORDER BY city_name"):
        p = current_payload(c["city_name"])
        if p:
            out.append({"city": p["city"], "aqi": p["aqi"], "label": p["label"], "time": p["time"], "stale": p["stale"]})
    return jsonify(out)


@app.route("/api/trend")
def trend():
    """Trends page (UC-03, FR-03): daily averages plus the average, highest and lowest value.
    Use ?days=7 (or 14, 30), or ?start=2018-03-01&end=2018-03-31 for a custom range."""
    city = request.args.get("city", "Kathmandu")
    start, end = request.args.get("start"), request.args.get("end")
    if start or end:  # custom date range
        try:
            first, last = date.fromisoformat(start), date.fromisoformat(end)
        except (TypeError, ValueError):
            return error("Give both dates like 2018-03-01.")
        if first > last:
            return error("The start date must be before the end date.")
        if (last - first).days > 730:
            return error("Pick a range of 2 years or less.")
        rows = range_series(city, first, last)
        if not rows:
            return error(f"No readings for {city} between {first} and {last}.", 404)
    else:  # ready-made range
        days = request.args.get("days", 7, type=int)
        if days not in (7, 14, 30):
            return error("days must be 7, 14, or 30.")
        rows = daily_series(city, days)
        if not rows:
            return error(f"No readings yet for {city}.", 404)
    return jsonify({
        "city": city,
        "days": [{"date": str(r["day"]), "aqi": int(r["aqi"])} for r in rows],
        "stats": trend_stats([{"day": r["day"], "aqi": int(r["aqi"])} for r in rows]),
    })


@app.route("/api/compare")
def compare():
    """Compare page (UC-04, FR-04): the newest reading of two cities, and optionally a third (&c=...)."""
    a, b, c = request.args.get("a"), request.args.get("b"), request.args.get("c")
    if not a or not b:
        return error("Give two cities: ?a=Kathmandu&b=Pokhara (and optionally &c=Lalitpur)")
    da, db_ = current_payload(a), current_payload(b)
    dc = current_payload(c) if c else None
    if not da or not db_ or (c and not dc):
        return error("One of the cities has no readings yet.", 404)
    return jsonify({"a": da, "b": db_, "c": dc})


@app.route("/api/predict")
def predict():
    """Prediction page (UC-05, FR-05): estimate for tomorrow and the day after.
    The estimate is a straight line through the last 7 daily averages (see analysis.py)."""
    city = request.args.get("city", "Kathmandu")
    rows = daily_series(city, 7)
    values = [int(r["aqi"]) for r in rows]
    est = predict_next(values)
    if est is None:  # fewer than 3 days of data
        return error(f"Not enough data yet for {city}: {len(values)} day(s) of readings in the last 7 days, and at least 3 are needed.", 404)
    last_day = rows[-1]["day"]
    today_cat = category(values[-1])
    out = []
    for k, v in enumerate(est, start=1):  # k = 1 is tomorrow, k = 2 is the day after
        cat = category(v)
        out.append({"date": str(last_day + timedelta(days=k)), "aqi": v, "label": cat["label"]})
    return jsonify({
        "city": city,
        "history": [{"date": str(r["day"]), "aqi": int(r["aqi"])} for r in rows],
        "today": {"date": str(last_day), "aqi": values[-1], "label": today_cat["label"]},
        "tomorrow": out[0],
        "day_after": out[1],
    })


def month_range(first, last):
    """All months from first to last as 'YYYY-MM', so months with no data show up as gaps in the chart."""
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


@app.route("/api/history")
def history():
    """History page: monthly averages and yearly summaries over all the stored data of a city."""
    city = request.args.get("city", "Kathmandu")
    # One row per month: average AQI, highest AQI and the number of days that have data
    rows = query(
        "SELECT DATE_FORMAT(r.`timestamp`, '%%Y-%%m') AS month, ROUND(AVG(r.aqi_value)) AS avg_aqi, "
        "MAX(r.aqi_value) AS max_aqi, COUNT(DISTINCT DATE(r.`timestamp`)) AS days "
        "FROM aq_reading r JOIN location l ON l.location_id = r.location_id "
        "WHERE l.city_name = %s GROUP BY month ORDER BY month", (city,))
    if not rows:
        return error(f"No readings yet for {city}.", 404)
    cats = query("SELECT aqi_min, aqi_max, label FROM health_category")

    def label_for(aqi):
        return next((c["label"] for c in cats if c["aqi_min"] <= aqi <= c["aqi_max"]), "Unknown")

    # Fill the months without data with empty entries, so they appear as gaps
    by_month = {r["month"]: r for r in rows}
    months = []
    for m in month_range(rows[0]["month"], rows[-1]["month"]):
        r = by_month.get(m)
        if r:
            avg = int(r["avg_aqi"])
            months.append({"month": m, "avg": avg, "max": int(r["max_aqi"]), "days": int(r["days"]), "label": label_for(avg)})
        else:
            months.append({"month": m, "avg": None, "max": None, "days": 0, "label": None})

    # One summary per year, with the worst month (only months with at least 10 days of data count)
    year_rows = query(
        "SELECT YEAR(r.`timestamp`) AS y, ROUND(AVG(r.aqi_value)) AS avg_aqi, "
        "COUNT(DISTINCT DATE(r.`timestamp`)) AS days "
        "FROM aq_reading r JOIN location l ON l.location_id = r.location_id "
        "WHERE l.city_name = %s GROUP BY y ORDER BY y", (city,))
    years = []
    for y in year_rows:
        yr, avg = int(y["y"]), int(y["avg_aqi"])
        full = [m for m in months if m["month"].startswith(str(yr)) and m["avg"] is not None and m["days"] >= 10]
        worst = max(full, key=lambda m: m["avg"]) if full else None
        years.append({"year": yr, "avg": avg, "days": int(y["days"]), "label": label_for(avg),
                      "worst_month": worst["month"] if worst else None, "worst_avg": worst["avg"] if worst else None})

    sources = [r["source_name"] for r in query(
        "SELECT DISTINCT s.source_name FROM aq_reading r JOIN data_source s ON s.source_id = r.source_id "
        "JOIN location l ON l.location_id = r.location_id WHERE l.city_name = %s ORDER BY s.source_name", (city,))]
    return jsonify({"city": city, "from": months[0]["month"], "to": months[-1]["month"],
                    "sources": sources, "months": months, "years": years})


# ---------------------------------------------------------------------------
# Live data refresh (FR-01, UC-01)
# ---------------------------------------------------------------------------
_refresh_lock = threading.Lock()   # makes sure two refreshes never run at the same time
_last_refresh = 0.0                # when the last refresh happened
MIN_GAP_SECONDS = 60               # the button works at most once a minute, to protect the data source


@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Fetches live data now. This is what the 'Update live data' button calls.
    It runs the same job as the collector script (collector.py)."""
    global _last_refresh
    with _refresh_lock:
        wait = MIN_GAP_SECONDS - (time.time() - _last_refresh)
        if wait > 0:
            return error(f"Data was just updated. Try again in {int(wait) + 1} seconds.", 429)
        try:
            results = collect_once()
        except RuntimeError as e:  # for example the token is missing
            return error(str(e), 400)
        _last_refresh = time.time()
    return jsonify({"saved": sum(r.get("new", 0) for r in results), "results": results})


def auto_refresh(minutes):
    """Background loop: fetch live data every `minutes` minutes while the server is running."""
    while True:
        try:
            collect_once()
        except Exception as e:  # keep the loop alive if the source or database is down for a while
            print("Automatic refresh failed:", e)
        time.sleep(minutes * 60)


if __name__ == "__main__":
    # AUTO_REFRESH_MINUTES in the .env file switches on automatic fetching (0 means off)
    minutes = int(os.getenv("AUTO_REFRESH_MINUTES", "0") or 0)
    # In debug mode Flask starts two processes; only the real one (WERKZEUG_RUN_MAIN) should start the loop
    if minutes > 0 and os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Thread(target=auto_refresh, args=(minutes,), daemon=True).start()
    app.run(debug=True, port=int(os.getenv("PORT", "5001")))
