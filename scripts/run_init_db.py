"""Chay init_db.sql tren Neon PostgreSQL."""
import psycopg
from config import settings

conn = psycopg.connect(settings.database_url)
conn.autocommit = True
cur = conn.cursor()

with open("scripts/init_db.sql", "r") as f:
    sql = f.read()
    cur.execute(sql)

# Kiem tra cac bang da tao
cur.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' ORDER BY table_name"
)
tables = [r[0] for r in cur.fetchall()]
print(f"Cac bang da tao: {tables}")
print(f"Tong: {len(tables)} bang")

cur.close()
conn.close()
