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
   For real readings: `python backend/collector.py` (add `--every 60` to repeat every hour).
   The page footer shows "Sample data" whenever the latest reading is sample data.
6. Start the app: `python backend/app.py`, then open http://127.0.0.1:5000
7. Before using real data for the final demo, remove the sample readings: `python backend/sample_data.py --clear`

## Data
1. **Sample data (made-up, for demos):** `data/sample_readings.csv`, 5 cities, 30 days. Import it with
   `python backend/import_csv.py data/sample_readings.csv --source "Sample data"`, or just run `python backend/sample_data.py`.
2. **Real historical data (Kathmandu, Jan 2015 to Mar 2021):** Open Data Nepal, "Air Quality Data in Kathmandu", licence CC BY-SA (credit them in the report).
   - US Embassy station (8.3 MB): https://opendatanepal.com/dataset/bf246006-59ec-4013-aa38-a9d83a6e80bb/resource/042b8821-1117-44cc-b007-e8633ae64702/download/aq_kathmandu_us-diplomatic-post_embassy_kathmandu.csv
   - Phora Durbar station (8.7 MB): https://opendatanepal.com/dataset/bf246006-59ec-4013-aa38-a9d83a6e80bb/resource/0d91e90d-db6a-4c23-9274-96c757aaedae/download/aq_kathmandu_us_diplomatic_post_phora_durbar_kathmandu.csv

   Download a file, then:
   `python backend/import_csv.py us_embassy.csv --city Kathmandu --source "Open Data Nepal (US Embassy)" --url "https://opendatanepal.com/dataset/air-quality-data-in-kathmandu"`
   The importer reads wide files (one column per pollutant) and long files (columns `parameter` and `value`). If the file has no AQI column it works AQI out from PM2.5 with the US EPA formula. Missing-value codes like -999 are ignored.
3. **Live data (2026):** `python backend/collector.py` with your aqicn.org token.

The pages count "the last 7 days" back from the newest reading of the city, so old data still shows. The footer shows the date of that newest reading, so it is always clear how old the data is.

## API
- `GET /api/cities`
- `GET /api/current?city=Kathmandu`
- `GET /api/trend?city=Kathmandu&days=7` (days: 7, 14, or 30)
- `GET /api/compare?a=Kathmandu&b=Pokhara`
- `GET /api/predict?city=Kathmandu` (needs at least 3 days of readings)

## Who does what
- Sujit: `database/` and `backend/collector.py`
- Dipa: `backend/app.py` and `backend/analysis.py`
- Raveen: `frontend/` and documentation

## Git
One branch per person (for example `sujit-database`, `dipa-api`, `raveen-frontend`). Commit small and often, open a pull request, and merge to `main` after another member has looked at it.

## Status (Week 7)
- Done: database schema and seed, API with all 5 endpoints, trend statistics, prediction, frontend connected to the API, error messages when data or the database is missing.
- Not done yet: running the importer on the real Open Data Nepal files (the file layout was not checked), running the collector against the live aqicn.org API with a real token, scheduled collection, automated tests, deployment.
