"""Import air quality readings from a CSV file into the database.

Examples:
  python backend/import_csv.py data/sample_readings.csv --source "Sample data"
  python backend/import_csv.py data/real/EmbassyKathmandu_PM2.5_2017.csv data/real/EmbassyKathmandu_PM2.5_2018.csv --city Kathmandu --source "US Embassy Kathmandu (AirNow)"

The file can be "wide" (one column per pollutant) or "long" (columns named parameter and value).
If the file has no AQI column, AQI is worked out from PM2.5 with the US EPA formula.
"""
import argparse
import re
import sys
import pandas as pd
from db import get_conn

# Different files name the same pollutant differently (ozone or o3, aqi or aqius ...).
# This table turns every name into one standard name.
ALIASES = {"pm25": "pm25", "pm10": "pm10", "o3": "o3", "ozone": "o3", "no2": "no2", "so2": "so2",
           "co": "co", "aqi": "aqi", "aqivalue": "aqi", "aqius": "aqi"}
# Column names that may hold the date and time, and the city. The first one found in the file is used.
TIME_NAMES = ["timestamp", "datetime", "datelocal", "datelt", "local", "date", "time", "dateutc", "utc"]
CITY_NAMES = ["city", "cityname", "location"]
POLLUTANTS = ["pm25", "pm10", "o3", "no2", "so2", "co"]
# US EPA table that turns a PM2.5 value (ug/m3) into an AQI number: (from, to, AQI from, AQI to)
PM25_BREAKPOINTS = [(0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), (55.5, 150.4, 151, 200),
                    (150.5, 250.4, 201, 300), (250.5, 350.4, 301, 400), (350.5, 500.4, 401, 500)]


def norm(name):
    """Makes a column name easy to compare: lower case, letters and digits only ('Date (LT)' becomes 'datelt')."""
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
    """Reads one CSV file and returns a table with one row per city and time, and one column per pollutant."""
    df = pd.read_csv(path)
    cols = {norm(c): c for c in df.columns}
    tcol = next((cols[n] for n in TIME_NAMES if n in cols), None)
    if tcol is None:
        sys.exit("Could not find a date/time column. Columns found: " + ", ".join(df.columns))
    ccol = next((cols[n] for n in CITY_NAMES if n in cols), None)
    t = pd.to_datetime(df[tcol], errors="coerce")
    if getattr(t.dt, "tz", None) is not None:  # times with a time zone are converted to Nepal time
        t = t.dt.tz_convert("Asia/Kathmandu").dt.tz_localize(None)
    df["ts"] = t
    valcol = cols.get("value") or cols.get("rawconc")
    if "parameter" in cols and valcol:  # long format (also the AirNow layout: Parameter, Raw Conc., AQI)
        if "qcname" in cols:  # AirNow marks each hour Valid, Invalid, Missing, or Suspect; keep only Valid
            df = df[df[cols["qcname"]].astype(str).str.strip().str.lower() == "valid"]
        # AirNow writes "PM2.5 - Principal", so only the part before " - " is the pollutant name
        df["param"] = df[cols["parameter"]].map(lambda x: ALIASES.get(norm(str(x).split(" - ")[0])))
        df = df.dropna(subset=["ts", "param"])
        # Ozone is stored in ppb. OpenAQ files give ozone in ppm, so those values are multiplied by 1000.
        ucol = cols.get("unit") or cols.get("concunit")
        if ucol:
            ppm = (df["param"] == "o3") & (df[ucol].astype(str).str.strip().str.lower() == "ppm")
            df.loc[ppm, valcol] = df.loc[ppm, valcol] * 1000
        keys = ["ts"] + ([ccol] if ccol else [])
        wide = df.pivot_table(index=keys, columns="param", values=valcol, aggfunc="mean").reset_index()
        if "aqi" in cols:  # AirNow gives an AQI per pollutant; the PM2.5 one is our overall AQI
            pm = df[df["param"] == "pm25"].copy()
            pm["aqi_pm"] = pd.to_numeric(pm[cols["aqi"]], errors="coerce")
            pm = pm[pm["aqi_pm"] >= 0].groupby(keys)["aqi_pm"].mean().reset_index().rename(columns={"aqi_pm": "aqi"})
            wide = wide.merge(pm, on=keys, how="left")
        wide = wide.rename(columns={ccol: "city_key"} if ccol else {})
    else:  # wide format: one column per pollutant, already one row per time
        ren = {c: ALIASES[norm(c)] for c in df.columns if norm(c) in ALIASES}
        wide = df.rename(columns=ren)
        wide = wide.rename(columns={ccol: "city_key"} if ccol else {})
        wide = wide.dropna(subset=["ts"])
    for p in POLLUTANTS + ["aqi"]:
        if p not in wide.columns:
            wide[p] = None
    return wide


def main():
    """Reads the files, cleans the values and saves them in the AQ_READING table."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="one or more CSV files (they are merged by time)")
    ap.add_argument("--city", help="city name. Always used when given, so a station name in the file does not matter")
    ap.add_argument("--from", dest="start", help="skip readings before this date, for example 2019-01-02 (avoids overlap with data already imported)")
    ap.add_argument("--source", required=True, help="name of the data source, for example 'Open Data Nepal (US Embassy)'")
    ap.add_argument("--url", default="imported from a CSV file", help="where the file came from")
    a = ap.parse_args()

    frames = []
    for f in a.files:
        w = read_readings(f)
        if a.city:
            w["city_key"] = a.city
        elif "city_key" not in w.columns:
            sys.exit("The file has no city column. Add --city Kathmandu")
        if a.start:
            w = w[w["ts"] >= pd.Timestamp(a.start)]
        frames.append(w)
    # Join all files, and keep one row per city and time (the first value found for each pollutant)
    wide = pd.concat(frames, ignore_index=True).groupby(["city_key", "ts"], as_index=False).first()

    conn = get_conn()
    saved = skipped = 0
    with conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO data_source (source_name, source_url) VALUES (%s, %s)", (a.source, a.url))
        cur.execute("SELECT source_id FROM data_source WHERE source_name = %s", (a.source,))
        sid = cur.fetchone()["source_id"]
        cur.execute("SELECT city_name, location_id FROM location")
        loc = {r["city_name"].lower(): r["location_id"] for r in cur.fetchall()}
        batch = []
        for r in wide.itertuples(index=False):  # one database row per reading
            row = r._asdict()
            lid = loc.get(str(row["city_key"]).strip().lower())
            vals = [clean(row[p]) for p in POLLUTANTS]
            aqi = clean(row["aqi"], 500)
            aqi = round(aqi) if aqi is not None else pm25_to_aqi(vals[0])
            if lid is None or aqi is None:
                skipped += 1
                continue
            batch.append((lid, sid, row["ts"].to_pydatetime(), *vals, int(aqi)))
        # Save in batches of 1000. INSERT IGNORE skips readings that are already in the table.
        for i in range(0, len(batch), 1000):
            cur.executemany(
                "INSERT IGNORE INTO aq_reading (location_id, source_id, `timestamp`, pm25, pm10, o3, no2, so2, co, aqi_value) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", batch[i:i + 1000])
            saved += cur.rowcount
    conn.close()
    print(f"Saved {saved} reading(s). Skipped {skipped} row(s) with no AQI or an unknown city.")
    if len(wide):
        print(f"The files cover {wide['ts'].min():%Y-%m-%d} to {wide['ts'].max():%Y-%m-%d}.")


if __name__ == "__main__":
    main()