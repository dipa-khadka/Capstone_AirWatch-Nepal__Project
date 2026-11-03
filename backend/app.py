"""AirWatch Nepal backend (Flask REST API). Run:  python backend/app.py"""
import os
from datetime import timedelta
import pymysql
from flask import Flask, jsonify, request, send_from_directory
from db import query
from analysis import trend_stats, predict_next

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=FRONTEND, static_url_path="")

POLLUTANTS = {"pm25": "PM2.5", "pm10": "PM10", "o3": "O3", "no2": "NO2", "so2": "SO2", "co": "CO"}


def error(msg, code=400):
    return jsonify({"error": msg}), code


@app.errorhandler(pymysql.err.OperationalError)
def database_down(_):
    return error("Cannot reach the database. Check that MySQL is running and the .env settings are correct.", 503)


def category(aqi):
    rows = query("SELECT label, message FROM health_category WHERE %s BETWEEN aqi_min AND aqi_max", (aqi,))
    return rows[0] if rows else {"label": "Unknown", "message": ""}


def latest_reading(city):
    rows = query(
        "SELECT r.*, l.city_name, s.source_name FROM aq_reading r "
        "JOIN location l ON l.location_id = r.location_id JOIN data_source s ON s.source_id = r.source_id "
        "WHERE l.city_name = %s ORDER BY r.`timestamp` DESC LIMIT 1", (city,))
    return rows[0] if rows else None


def current_payload(city):
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
        "source": r["source_name"],
        "pollutants": {name: (float(r[col]) if r[col] is not None else None) for col, name in POLLUTANTS.items()},
    }


def daily_series(city, days):
    """Daily average AQI for the last `days` days, counted back from the newest reading of that city."""
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


@app.route("/")
def home():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/api/cities")
def cities():
    return jsonify(query("SELECT location_id AS id, city_name AS name, district FROM location ORDER BY city_name"))


@app.route("/api/current")
def current():
    city = request.args.get("city", "Kathmandu")
    data = current_payload(city)
    return jsonify(data) if data else error(f"No readings yet for {city}.", 404)


@app.route("/api/trend")
def trend():
    city = request.args.get("city", "Kathmandu")
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
    a, b = request.args.get("a"), request.args.get("b")
    if not a or not b:
        return error("Give two cities: ?a=Kathmandu&b=Pokhara")
    da, db_ = current_payload(a), current_payload(b)
    if not da or not db_:
        return error("One of the cities has no readings yet.", 404)
    return jsonify({"a": da, "b": db_})


@app.route("/api/predict")
def predict():
    city = request.args.get("city", "Kathmandu")
    rows = daily_series(city, 7)
    values = [int(r["aqi"]) for r in rows]
    est = predict_next(values)
    if est is None:
        return error("Not enough data yet. At least 3 days of readings are needed.", 404)
    last_day = rows[-1]["day"]
    today_cat = category(values[-1])
    out = []
    for k, v in enumerate(est, start=1):
        cat = category(v)
        out.append({"date": str(last_day + timedelta(days=k)), "aqi": v, "label": cat["label"]})
    return jsonify({
        "city": city,
        "history": [{"date": str(r["day"]), "aqi": int(r["aqi"])} for r in rows],
        "today": {"date": str(last_day), "aqi": values[-1], "label": today_cat["label"]},
        "tomorrow": out[0],
        "day_after": out[1],
    })


if __name__ == "__main__":
    app.run(debug=True)
