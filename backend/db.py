"""Database helper: the one place that knows how to connect to MySQL.
All other files call query(...) from here, so the connection details are not repeated.
The settings (host, user, password, database name) come from the .env file in the project folder."""
import os
import pymysql
from dotenv import load_dotenv

# Read the .env file so os.getenv(...) below can see the values
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def get_conn():
    """Opens a new connection to the MySQL database."""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "airwatch"),
        cursorclass=pymysql.cursors.DictCursor,  # rows come back as dictionaries, for example row["aqi_value"]
        autocommit=True,                          # save changes right away
    )


def query(sql, params=None):
    """Runs one SQL question and returns all the rows.
    Values go in `params` (and %s in the SQL) instead of being pasted into the text.
    This is what protects the database from SQL injection."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()  # always close the connection, even if the query failed
