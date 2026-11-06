# AirWatch Nepal (Week 7 starter)

Air pollution trend analysis and prediction for Nepali cities. Python (Flask) backend, MySQL database, HTML/CSS/JavaScript + Chart.js frontend.

## Folder structure
```
airwatch-nepal/
  database/schema.sql      the 4 tables from our Week 5 physical design
  database/seed.sql        cities, data source, and the 6 health categories
  backend/app.py           Flask API (also serves the website)
  backend/analysis.py      trend statistics and the 2-day prediction (pandas, scikit-learn)
  backend/collector.py     gets real readings from aqicn.org and saves them
  backend/sample_data.py   fills the database with made-up readings for demos
  backend/import_csv.py    imports readings from a CSV file (sample or real data)
  data/sample_readings.csv the made-up demo data as a CSV you can open in Excel
  backend/db.py            MySQL connection
  frontend/index.html      the 4 pages (Home, Trends, Compare, Prediction)
  frontend/style.css       all the styling (colours, layout, animations)
  frontend/app.js          the page logic (calls the API, draws the charts)
```

## Run it (Windows)
Use **Command Prompt** (cmd), not PowerShell, and open it inside the project folder (in VS Code: Terminal, New Terminal, choose Command Prompt). PowerShell does not support the `<` used in step 4.

1. Install Python 3.11+ and MySQL 8 (or XAMPP). Make sure MySQL is running.
2. In the project folder:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`. Set `DB_PASSWORD` (your MySQL password) and `WAQI_TOKEN` (free token: https://aqicn.org/data-platform/token/).
4. Create the database:
   ```
   mysql -u root -p < database/schema.sql
   mysql -u root -p < database/seed.sql
   ```
   If Windows says `mysql` is not recognized, run the same two files from MySQL Workbench instead (File, Open SQL Script, then the lightning button), or from phpMyAdmin if you use XAMPP (Import tab).
5. Add data. For a demo with made-up numbers: `python backend/sample_data.py`.
   For real readings: `python backend/collector.py` (add `--every 60` to repeat every hour), or click **Update live data** on the website.
   To fetch live data automatically while the website runs, set `AUTO_REFRESH_MINUTES=60` in `.env`.
   The page footer shows "Sample data" whenever the latest reading is sample data.
6. Start the app: `python backend/app.py`, then open http://127.0.0.1:5001
7. Before using real data for the final demo, remove the sample readings: `python backend/sample_data.py --clear`

## Data
1. **Sample data (made-up, for demos):** `data/sample_readings.csv`, 5 cities, 30 days. Import it with
   `python backend/import_csv.py data/sample_readings.csv --source "Sample data"`, or just run `python backend/sample_data.py`.
2. **Real historical data (Kathmandu, 21 Feb 2017 to 1 Jan 2019):** hourly PM2.5 and ozone from the US Embassy and Phora Durbar monitors, published by US EPA AirNow and collected in https://github.com/hbvj99/EPAAirPollution (credit them in the report). The 8 files are already in `data/real/`. With the database created and MySQL running, run these two commands from the project folder (Command Prompt, venv active):

   `python backend/import_csv.py data/real/EmbassyKathmandu_PM2.5_2017.csv data/real/EmbassyKathmandu_PM2.5_2018.csv data/real/EmbassyKathmandu_OZONE_2017.csv data/real/EmbassyKathmandu_OZONE_2018.csv --city Kathmandu --source "US Embassy Kathmandu (AirNow)" --url "https://github.com/hbvj99/EPAAirPollution"`

   `python backend/import_csv.py data/real/PhoraDurbarKathmandu_PM2.5_2017.csv data/real/PhoraDurbarKathmandu_PM2.5_2018.csv data/real/PhoraDurbarKathmandu_OZONE_2017.csv data/real/PhoraDurbarKathmandu_OZONE_2018.csv --city Kathmandu --source "Phora Durbar Kathmandu (AirNow)" --url "https://github.com/hbvj99/EPAAirPollution"`

   Expected: `Saved 15411 reading(s). Skipped 615 row(s)...` and `Saved 15722 reading(s). Skipped 407 row(s)...`. Hours that AirNow marks Invalid or Missing are skipped. Only PM2.5 and ozone exist in these files, so the other pollutants stay empty. Ozone is in ppb and PM2.5 in ug/m3.
   Run `python backend/sample_data.py --clear` first, because the pages show the newest data, and sample data (2026) is newer than this.
   The importer also reads other files: wide (one column per pollutant) and long (columns `parameter` and `value`). If a file has no AQI column it works AQI out from PM2.5 with the US EPA formula. Missing-value codes like -999 are ignored.
3. **Real historical data, 2015 to March 2021 (fills 2019 to 2021):** Open Data Nepal, dataset "Air Quality Data in Kathmandu" (https://opendatanepal.com/dataset/air-quality-data-in-kathmandu, license CC BY-SA, collected from OpenAQ). Download the two CSV files in your browser (US Embassy and Phora Durbar), put them in `data/real/`, then run:

   `python backend/import_csv.py data/real/aq_kathmandu_us-diplomatic-post_embassy_kathmandu.csv --city Kathmandu --source "US Embassy Kathmandu (AirNow)" --url "https://opendatanepal.com/dataset/air-quality-data-in-kathmandu"`

   `python backend/import_csv.py data/real/aq_kathmandu_us_diplomatic_post_phora_durbar_kathmandu.csv --city Kathmandu --source "Phora Durbar Kathmandu (AirNow)" --url "https://opendatanepal.com/dataset/air-quality-data-in-kathmandu"`

   Using the same source names as step 2 means hours that are already in the database are ignored. The last line printed shows which dates the files cover. Add `--from 2019-01-02` to import only the new part.
4. **Real historical data, March 2021 to now:** OpenAQ (https://explore.openaq.org, free account) has the US Embassy Kathmandu and Phora Durbar stations with data up to 2026. Download each station's CSV for the years you need and import it the same way with `--city Kathmandu`.
5. **Live data (2026):** needs your aqicn.org token in `.env`. Three ways to fetch it: the **Update live data** button on the website (at most once a minute), `python backend/collector.py` (add `--every 60` to repeat), or `AUTO_REFRESH_MINUTES=60` in `.env` so the server fetches by itself while it runs. All of them save into the same table, and saving the same reading twice is ignored.

The pages count "the last 7 days" back from the newest reading of the city, so old data still shows. The footer shows the date of that newest reading, so it is always clear how old the data is.

## Cities
`database/seed.sql` has 15 Nepali cities: Kathmandu, Pokhara, Bhaktapur, Lalitpur, Bharatpur, Biratnagar, Janakpur, Nepalgunj, Dhangadhi, Lumbini, Dhankuta, Surkhet, Dhulikhel, Ghorahi, Itahari. If your database already exists, run `database/seed.sql` again to add the new ones (nothing is deleted).
A city shows up in the website menus only after it has at least one reading. The collector asks aqicn.org for the station nearest to each city and skips it if that station is more than 25 km away, so a city never shows another city's air. The Update live data message lists which cities got data and which were skipped. Only Kathmandu has historical data from 2017 on; the other cities have data from the day you first collect it.

## API
- `GET /api/cities`
- `GET /api/current?city=Kathmandu`
- `GET /api/overview` (newest AQI of every city that has data; used by the Air across Nepal tiles on Home)
- `GET /api/trend?city=Kathmandu&days=7` (days: 7, 14, or 30), or `&start=2018-03-01&end=2018-03-31` for a custom range of up to 2 years
- `GET /api/history?city=Kathmandu` (monthly and yearly averages over all the data; used by the History page)
- `POST /api/refresh` (fetches live data from aqicn.org now; used by the Update live data button, needs WAQI_TOKEN)
- `GET /api/compare?a=Kathmandu&b=Pokhara` (add `&c=Lalitpur` for a third city)
- `GET /api/predict?city=Kathmandu` (needs at least 3 days of readings)

## Who does what
- Sujit: `database/` and `backend/collector.py`
- Dipa: `backend/app.py` and `backend/analysis.py`
- Raveen: `frontend/` and documentation

## Git
One branch per person (for example `sujit-database`, `dipa-api`, `raveen-frontend`). Commit small and often, open a pull request, and merge to `main` after another member has looked at it.

## Status (Week 7)
- Done: database schema and seed, API with all 5 endpoints, trend statistics, prediction, frontend connected to the API, error messages when data or the database is missing.
- Done and tested: importing the real 2017-2018 Kathmandu files (31,133 readings).
- Not done yet: running the collector against the live aqicn.org API with a real token, scheduled collection, automated tests, deployment.
