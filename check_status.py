#!/usr/bin/env python3
"""Script para verificar el estado de los registros en la base de datos"""
import os
from dotenv import load_dotenv
import pymysql

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
        with conn.cursor() as cur:
            print("\n=== ESTADO DE REGISTROS EN LA BASE DE DATOS ===\n")
            cur.execute("SELECT p.ocr_status, COUNT(*) as cnt FROM pdf_metadata p GROUP BY p.ocr_status")
            rows = cur.fetchall()
            for row in rows:
                print(f"{row['ocr_status']}: {row['cnt']}")
            
            cur.execute("SELECT COUNT(*) as cnt FROM pdf_metadata WHERE ocr_status='pending'")
            pending = cur.fetchone()['cnt']
            print(f"\nRegistros pendientes disponibles: {pending}")
            
            # Mostrar algunos ejemplos
            cur.execute("SELECT n.path FROM nodes n JOIN pdf_metadata p ON n.id=p.node_id WHERE p.ocr_status='pending' LIMIT 5")
            examples = cur.fetchall()
            if examples:
                print("\nEjemplos de archivos pendientes:")
                for ex in examples:
                    print(f"  - {ex['path']}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
