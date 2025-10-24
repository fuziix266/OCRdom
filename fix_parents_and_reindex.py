#!/usr/bin/env python3
"""Fix parent folder nodes for a sample of pending files and assign tree_index.

Usar para preparar una muestra (no escanea todo el árbol): toma N filas con
ocr_status='pending', crea nodos de carpeta faltantes y ejecuta reindexado.
"""
from pathlib import Path
import os
from dotenv import load_dotenv
import pymysql
import sys

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

def get_pending(conn, limit=20):
    with conn.cursor() as cur:
        cur.execute("SELECT n.id as node_id, n.path as path FROM nodes n JOIN pdf_metadata p ON n.id=p.node_id WHERE p.ocr_status='pending' ORDER BY n.path ASC LIMIT %s", (limit,))
        return cur.fetchall()

def ensure_folder_node_local(conn, rel_dir):
    # replicate minimal logic to create folder nodes
    cur = conn.cursor()
    cur.execute("SELECT id FROM nodes WHERE path=%s AND is_dir=1", (rel_dir,))
    r = cur.fetchone()
    if r:
        return r['id']
    parent = str(Path(rel_dir).parent).replace('\\', '/') if Path(rel_dir).parent != Path('.') else None
    parent_id = None
    if parent:
        parent_id = ensure_folder_node_local(conn, parent)
    cur.execute("INSERT INTO nodes (parent_id, name, path, is_dir, created_at, updated_at) VALUES (%s,%s,%s,1,NOW(),NOW())", (parent_id, Path(rel_dir).name, rel_dir))
    conn.commit()
    return cur.lastrowid

def assign_tree_index_local(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM nodes ORDER BY path ASC")
        rows = cur.fetchall()
        idx = 1
        for r in rows:
            cur.execute("UPDATE nodes SET tree_index=%s WHERE id=%s", (idx, r['id']))
            idx += 1
    conn.commit()

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    conn = pymysql.connect(**DB_CONF)
    try:
        rows = get_pending(conn, limit)
        if not rows:
            print('No pending rows found')
            return
        print(f'Found {len(rows)} pending files; ensuring parent folders...')
        for r in rows:
            path = r['path']
            parent = str(Path(path).parent)
            if parent and parent != '.':
                ensure_folder_node_local(conn, parent.replace('\\', '/'))
        print('Assigning tree_index...')
        assign_tree_index_local(conn)
        print('Done')
    finally:
        conn.close()

if __name__ == '__main__':
    main()
