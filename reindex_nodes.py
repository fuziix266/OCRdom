#!/usr/bin/env python3
from dotenv import load_dotenv
import pymysql
import os
from scan_transparencia import assign_tree_index

load_dotenv()

DB_CONF = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'ocr'),
    'autocommit': False,
    'cursorclass': pymysql.cursors.DictCursor,
}

def main():
    conn = pymysql.connect(**DB_CONF)
    try:
        assign_tree_index(conn)
        print('tree_index asignado')
    finally:
        conn.close()

if __name__ == '__main__':
    main()
