# AirWatch Nepal

**Air Pollution Trend Analysis and Prediction System** for 17 Nepali cities.
Capstone Project CAPR-F2026, Group 2 (Dipa Khadka, Sujit Shrestha, Raveen KC).

- **Website (live):** https://capstone-airwatch-nepal-project.onrender.com
  The site runs on a free server. If nobody has opened it for 15 minutes it goes to sleep, so the first visit can take about one minute to load. After that it is fast.
- **Code:** https://github.com/dipa-khadka/Capstone_AirWatch-Nepal__Project

## What the website does
| Page | What you can do | Requirement |
|---|---|---|
| Home | See the current AQI of a city, its health level, a short health message, advice for the day, the pollutants the station reports, and the AQI of all 17 cities ("Air across Nepal") | FR-02, FR-07 |
| Trends | See the daily AQI of a city for the last 7, 14 or 30 days, or for your own date range, with the average, highest and lowest value and a one-sentence summary | FR-03, FR-06 |
| History | See all stored data of a city: key numbers, a colour grid of every month, the yearly trend with the change from the year before, and a CSV download | FR-03, FR-06 |
| Compare | Compare 2 or 3 cities side by side | FR-04 |
| Prediction | Estimate the AQI of tomorrow and the day after from the last 7 days, with a one-sentence summary | FR-05 |
| Alert bar (every page) | Warns when a city has an AQI of 101 or higher in a fresh station reading (model estimates are never used for alerts) | FR-07 |
| Update live data button | Fetches the newest readings right now | FR-01 |

## Where the data comes from (please read)
Not all data is the same kind. The website shows which kind it is (History page: solid squares are station data, dotted squares are model estimates).

| Period | Cities | Source | Kind |
|---|---|---|---|
| 2017 to March 2021 | Kathmandu | US Embassy and Phora Durbar monitors (US EPA AirNow), taken from Open Data Nepal and https://github.com/hbvj99/EPAAirPollution | **Real station measurements** |
| August 2022 to 2025 | All 17 cities | Open-Meteo air quality API (CAMS model of Copernicus) | **Model estimate**, not a station measurement |
| October 2026 to now | Kathmandu, Lalitpur, Bhaktapur, Dhulikhel, Gaur, Siraha | aqicn.org live stations | **Real station measurements** (updated by GitHub Actions) |
| November 2026 to now | Every city that has no live station reading in the last 3 days | Open-Meteo current values (CAMS model), saved by the collector | **Model estimate**, labelled "estimate" on the website |

Known limits:
- There is no free public data for March 2021 to July 2022, so that period is empty.
- Only a few Nepali stations are live on aqicn.org. For a city with no live station reading in the last 3 days, the collector saves the current Open-Meteo model values instead (the last 7 days on the first run, then every new hour). The website marks them as "estimate", so every city has recent data and Prediction works for all cities. A city that has a recent station reading keeps its station data, and model values are not mixed into it.
- Alerts use station measurements only, because the model can be higher or lower than a station.
- If a station is offline, the website shows its last reading. A reading older than 24 hours is marked as old.
- The live stations report only PM2.5 and ozone. The database and collector can store PM10, NO2, SO2 and CO as well, and will do so when a station reports them.
- Model estimates can differ from a station, especially in the Kathmandu valley.
- Prediction is a simple trend estimate (a straight line through the last 7 daily averages), not a weather-style forecast. It only runs when the newest reading is at most 3 days old.

## How it is built
```
Browser (HTML, CSS, JavaScript, Chart.js)
        |  JSON
Flask API (Python)  ---  MySQL (4 tables)
        ^
        |  readings
Collector (aqicn.org live stations,
          Open-Meteo model as a fallback)  run by GitHub Actions on a schedule
```
- **Hosting:** website on Render, database on Aiven MySQL, collector on GitHub Actions.
- **Database tables:** LOCATION, AQ_READING, DATA_SOURCE, HEALTH_CATEGORY (Week 5 design).

```
airwatch-nepal/
  database/schema.sql          the 4 tables
  database/seed.sql            17 cities and the 6 health categories
  backend/app.py               Flask API, also serves the website
  backend/analysis.py          trend statistics and the 2-day prediction (pandas, scikit-learn)
  backend/collector.py         gets live readings from aqicn.org (and Open-Meteo model values for cities without a live station) and saves them
  backend/db.py                MySQL connection (local or cloud, set in .env)
  backend/setup_db.py          creates the tables and cities in whichever database .env points to
  backend/import_csv.py        imports readings from a CSV file
  backend/import_openmeteo.py  imports the Open-Meteo model data (2022 to 2025)
  backend/list_stations.py     shows which Nepali stations aqicn.org has (saves nothing)
  backend/check_live.py        shows the nearest live station of every city (saves nothing)
  backend/sample_data.py       made-up readings for demos
  frontend/index.html          the 5 pages
  frontend/style.css           colours and layout
  frontend/app.js              page logic, calls the API, draws the charts
  .github/workflows/collect.yml  runs the collector on a schedule
```

## Cloud setup (what runs the live website)
1. **Aiven MySQL:** create a MySQL service, then put its host, port, user, password and database name in `.env` and run `python backend/setup_db.py` once. Set `DB_SSL=true`.
2. **Render:** new Web Service from this GitHub repo. Build command `pip install -r requirements.txt`, start command `gunicorn --chdir backend --bind 0.0.0.0:$PORT app:app`. Environment variables: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL`, `WAQI_TOKEN`. Render deploys again by itself every time `main` changes.
3. **GitHub Actions:** the workflow `collect.yml` runs the collector. Add the same values as repository secrets. GitHub starts scheduled runs when it has room, so they come every few hours and not exactly every hour.

## API
- `GET /api/cities`
- `GET /api/current?city=Kathmandu`
- `GET /api/overview` (newest AQI of every city, used by the Home tiles and the alert bar)
- `GET /api/trend?city=Kathmandu&days=7` (days: 7, 14 or 30), or `&start=2019-03-01&end=2019-03-31` for a custom range of up to 2 years
- `GET /api/history?city=Kathmandu` (monthly and yearly averages, used by the History page)
- `POST /api/refresh` (fetches live data now, at most once a minute)
- `GET /api/compare?a=Kathmandu&b=Pokhara` (add `&c=Lalitpur` for a third city)
- `GET /api/predict?city=Kathmandu` (needs at least 3 days of readings in the last 7 days, and recent data)

## Who did what
- Sujit Shrestha: database and data collection
- Dipa Khadka: backend, trend analysis and prediction
- Raveen KC (project manager): frontend and documentation

## Developer setup (optional)
You do not need to run anything to see the project, the website above is already live. These steps are only for someone who wants to run their own copy on Windows.

1. Install Python 3.11+ and MySQL 8. Make sure MySQL is running.
2. In the project folder:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`. Set `DB_PASSWORD` (your MySQL password) and `WAQI_TOKEN` (free token: https://aqicn.org/data-platform/token/). Never put `.env` on GitHub.
4. Create the tables and cities:
   ```
   python backend/setup_db.py
   ```
5. Add data: `python backend/collector.py` for live readings, `python backend/import_openmeteo.py` for the 2022 to 2025 model data, `python backend/import_csv.py` for CSV files (see the notes in the file), or `python backend/sample_data.py` for made-up demo data.
6. Start the app: `python backend/app.py`, then open http://127.0.0.1:5001

## Credits
- Live data: World Air Quality Index Project (aqicn.org) and the stations behind it.
- Historical data: US EPA AirNow and the US Department of State monitors in Kathmandu, via Open Data Nepal (CC BY-SA) and https://github.com/hbvj99/EPAAirPollution.
- Model data (2022 to 2025 and the live fallback): Open-Meteo.com air quality API (CAMS, Copernicus Atmosphere Monitoring Service).
