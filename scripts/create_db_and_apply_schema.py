import os
import pymysql
from pathlib import Path

DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')
DB_NAME = os.environ.get('DB_NAME', 'ocr')

schema_path = Path(__file__).resolve().parents[1] / 'mariadb_schema.sql'
print('Usando conexión:', DB_HOST, DB_PORT, DB_USER, repr(DB_PASS), 'DB->', DB_NAME)
if not schema_path.exists():
    print('No se encontró el archivo de esquema en', schema_path)
    raise SystemExit(1)

# connect to server without specifying database to create it
conn = None
try:
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;")
        print('Base creada o ya existía:', DB_NAME)
    conn.close()

    # connect to the new database and apply schema
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME)
    with open(schema_path, 'r', encoding='utf-8') as fh:
        sql = fh.read()
    with conn.cursor() as cur:
        # execute statements split by ';' but keep safe for comments and empty
        stmts = [s.strip() for s in sql.split(';')]
        for s in stmts:
            if not s:
                continue
            try:
                cur.execute(s)
            except Exception as e:
                print('Error ejecutando statement:', e)
    conn.commit()
    print('Esquema aplicado correctamente en la base', DB_NAME)
except Exception as e:
    print('ERROR:', e)
    raise
finally:
    if conn:
        conn.close()
