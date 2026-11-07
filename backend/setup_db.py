"""Creates the tables and fills the fixed data (cities, data source, health levels) in the database
my .env file points to. Use it for an online database (Aiven, TiDB ...), where i cannot
open the .sql files in MySQL Workbench easily.

Run:  python backend/setup_db.py
It is safe to run again: existing tables and cities are kept.
"""
import os
from db import get_conn

ROOT = os.path.join(os.path.dirname(__file__), "..", "database")


def statements(path):
    """Reads an .sql file and returns its statements, without comments, CREATE DATABASE and USE lines
    (an online database already exists and has its own name)."""
    lines = []
    for line in open(path, encoding="utf8"):
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        if s.upper().startswith(("CREATE DATABASE", "USE ")):
            continue
        lines.append(line.rstrip("\n").split(" -- ")[0])
    return [x.strip() for x in "\n".join(lines).split(";") if x.strip()]


conn = get_conn()
with conn.cursor() as cur:
    for name in ("schema.sql", "seed.sql"):
        for sql in statements(os.path.join(ROOT, name)):
            cur.execute(sql)
        print("Done:", name)
    cur.execute("SELECT COUNT(*) AS n FROM location")
    print("Cities in the database:", cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) AS n FROM health_category")
    print("Health levels in the database:", cur.fetchone()["n"], "(should be 6)")
conn.close()