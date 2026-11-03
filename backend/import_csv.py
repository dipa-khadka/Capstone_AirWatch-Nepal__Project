"""Import air quality readings from a CSV file into the database.

Examples:
  python backend/import_csv.py data/sample_readings.csv --source "Sample data"
  python backend/import_csv.py us_embassy.csv --city Kathmandu --source "Open Data Nepal (US Embassy)"

The file can be "wide" (one column per pollutant) or "long" (columns named parameter and value).
If the file has no AQI column, AQI is worked out from PM2.5 with the US EPA formula.
"""
import argparse
import re
import sys
import pandas as pd
from db import get_conn

ALIASES = {"pm25": "pm25", "pm10": "pm10", "o3": "o3", "ozone": "o3", "no2": "no2", "so2": "so2",
           "co": "co", "aqi": "aqi", "aqivalue": "aqi", "aqius": "aqi"}
TIME_NAMES = ["timestamp", "datetime", "datelocal", "datelt", "local", "date", "time", "dateutc", "utc"]
CITY_NAMES = ["city", "cityname", "location"]
POLLUTANTS = ["pm25", "pm10", "o3", "no2", "so2", "co"]
PM25_BREAKPOINTS = [(0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), (55.5, 150.4, 151, 200),
                    (150.5, 250.4, 201, 300), (250.5, 350.4, 301, 400), (350.5, 500.4, 401, 500)]


def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def pm25_to_aqi(c):
    """US EPA AQI from a PM2.5 value (ug/m3)."""
    if c is None or pd.isna(c) or c < 0:
        return None
    c = int(c * 10) / 10
    for lo, hi, a, b in PM25_BREAKPOINTS:
        if lo <= c <= hi:
            return round((b - a) / (hi - lo) * (c - lo) + a)
    return 500 if c > 500.4 else None


def clean(v, top=9999.99):
    """Missing-value codes such as -999 and impossible numbers become empty."""
    if v is None or pd.isna(v) or v < 0 or v > top:
        return None
    return float(v)


def read_readings(path):
    df = pd.read_csv(path)
    cols = {norm(c): c for c in df.columns}
    tcol = next((cols[n] for n in TIME_NAMES if n in cols), None)
    if tcol is None:
        sys.exit("Could not find a date/time column. Columns found: " + ", ".join(df.columns))
    ccol = next((cols[n] for n in CITY_NAMES if n in cols), None)
    t = pd.to_datetime(df[tcol], errors="coerce")
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kathmandu").dt.tz_localize(None)
    df["ts"] = t
    if "parameter" in cols and "value" in cols:  # long format
        df["param"] = df[cols["parameter"]].map(lambda x: ALIASES.get(norm(x)))
        df = df.dropna(subset=["ts", "param"])
        keys = ["ts"] + ([ccol] if ccol else [])
        wide = df.pivot_table(index=keys, columns="param", values=cols["value"], aggfunc="mean").reset_index()
        wide = wide.rename(columns={ccol: "city_key"} if ccol else {})
    else:  # wide format
        ren = {c: ALIASES[norm(c)] for c in df.columns if norm(c) in ALIASES}
        wide = df.rename(columns=ren)
        wide = wide.rename(columns={ccol: "city_key"} if ccol else {})
        wide = wide.dropna(subset=["ts"])
    for p in POLLUTANTS + ["aqi"]:
        if p not in wide.columns:
            wide[p] = None
    return wide


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--city", help="city name, if the file has no city column")
    ap.add_argument("--source", required=True, help="name of the data source, for example 'Open Data Nepal (US Embassy)'")
    ap.add_argument("--url", default="imported from a CSV file", help="where the file came from")
    a = ap.parse_args()

    wide = read_readings(a.file)
    if "city_key" not in wide.columns:
        if not a.city:
            sys.exit("The file has no city column. Add --city Kathmandu")
        wide["city_key"] = a.city

    conn = get_conn()
    saved = skipped = 0
    with conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO data_source (source_name, source_url) VALUES (%s, %s)", (a.source, a.url))
        cur.execute("SELECT source_id FROM data_source WHERE source_name = %s", (a.source,))
        sid = cur.fetchone()["source_id"]
        cur.execute("SELECT city_name, location_id FROM location")
        loc = {r["city_name"].lower(): r["location_id"] for r in cur.fetchall()}
        batch = []
        for r in wide.itertuples(index=False):
            row = r._asdict()
            lid = loc.get(str(row["city_key"]).strip().lower())
            vals = [clean(row[p]) for p in POLLUTANTS]
            aqi = clean(row["aqi"], 500)
            aqi = round(aqi) if aqi is not None else pm25_to_aqi(vals[0])
            if lid is None or aqi is None:
                skipped += 1
                continue
            batch.append((lid, sid, row["ts"].to_pydatetime(), *vals, int(aqi)))
        for i in range(0, len(batch), 1000):
            cur.executemany(
                "INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, no2, so2, co, aqi_value) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", batch[i:i + 1000])
            saved += cur.rowcount
    conn.close()
    print(f"Saved {saved} reading(s). Skipped {skipped} row(s) with no AQI or an unknown city.")


if __name__ == "__main__":
    main()
