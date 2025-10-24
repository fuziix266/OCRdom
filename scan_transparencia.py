#!/usr/bin/env python3
"""
Script de escaneo para recorrer la carpeta 'transparencia/' y poblar MariaDB con
la estructura de árbol y metadatos de los PDFs.

Configuración por variables de entorno (ver README):
  DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME

Uso:
  python scan_transparencia.py --root /ruta/a/transparencia
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import pymysql
import pikepdf

load_dotenv()

DB_CONF = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'transparencia'),
    'autocommit': False,
    'cursorclass': pymysql.cursors.DictCursor,
}

def sha256_of_file(path, block_size=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def get_pdf_pages(path: Path):
    try:
        with pikepdf.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None

def ensure_tables(conn):
    # Intenta ejecutar el SQL de esquemas si existe
    schema_file = Path(__file__).with_name('mariadb_schema.sql')
    if schema_file.exists():
        with open(schema_file, 'r', encoding='utf-8') as fh:
            sql = fh.read()
        with conn.cursor() as cur:
            for stmt in sql.split(';'):
                s = stmt.strip()
                if s:
                    cur.execute(s)
        conn.commit()


def ensure_folder_node(conn, rel_dir: str):
    """Ensure that a node exists for a folder path and return its id.
    rel_dir should be a posix path without leading './' and not ending with '/'.
    """
    if not rel_dir:
        return None
    cur = conn.cursor()
    # If folder node exists, return id
    cur.execute("SELECT id FROM nodes WHERE path=%s AND is_dir=1", (rel_dir,))
    r = cur.fetchone()
    if r:
        return r['id']

    # find parent
    parent = str(Path(rel_dir).parent).replace('\\', '/') if Path(rel_dir).parent != Path('.') else None
    parent_id = None
    if parent:
        parent_id = ensure_folder_node(conn, parent)

    # insert folder node
    cur.execute(
        "INSERT INTO nodes (parent_id, name, path, is_dir, created_at, updated_at) VALUES (%s,%s,%s,1,NOW(),NOW())",
        (parent_id, Path(rel_dir).name, rel_dir)
    )
    conn.commit()
    return cur.lastrowid


def assign_tree_index(conn):
    """Assign a deterministic tree_index by ordering nodes.path ascending.
    This can be re-run to reindex.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM nodes ORDER BY path ASC")
        rows = cur.fetchall()
        idx = 1
        for r in rows:
            cur.execute("UPDATE nodes SET tree_index=%s WHERE id=%s", (idx, r['id']))
            idx += 1
    conn.commit()

def upsert_node_pdf(conn, root: Path, file_path: Path):
    rel = file_path.relative_to(root).as_posix()
    name = file_path.name
    stat = file_path.stat()
    size = stat.st_size
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
    checksum = sha256_of_file(file_path)
    pages = get_pdf_pages(file_path)

    with conn.cursor() as cur:
        cur.execute("SELECT id, checksum FROM nodes WHERE path=%s", (rel,))
        row = cur.fetchone()
        if row:
            node_id = row['id']
            old_checksum = row.get('checksum')
            if old_checksum != checksum:
                cur.execute(
                    "UPDATE nodes SET size=%s, mtime=%s, checksum=%s, updated_at=NOW() WHERE id=%s",
                    (size, mtime, checksum, node_id)
                )
                cur.execute("UPDATE pdf_metadata SET ocr_status='pending', updated_at=NOW() WHERE node_id=%s", (node_id,))
        else:
            # ensure parent folder node exists and get parent_id
            parent_path = str(Path(rel).parent) if Path(rel).parent != Path('.') else None
            parent_id = None
            if parent_path:
                parent_path = parent_path.replace('\\', '/')
                parent_id = ensure_folder_node(conn, parent_path)

            cur.execute(
                "INSERT INTO nodes (parent_id, name, path, is_dir, size, mtime, checksum, mime, extra) VALUES (%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (parent_id, name, rel, size, mtime, checksum, 'application/pdf', json.dumps({}))
            )
            node_id = cur.lastrowid
            cur.execute(
                "INSERT INTO pdf_metadata (node_id, pages, text_found, ocr_status) VALUES (%s,%s,0,'pending')",
                (node_id, pages)
            )
    conn.commit()

def scan(root: Path, limit: int = None):
    conn = pymysql.connect(**DB_CONF)
    try:
        ensure_tables(conn)
        processed = 0
        for p in root.rglob('*.pdf'):
            if limit and processed >= limit:
                break
            try:
                upsert_node_pdf(conn, root, p)
                processed += 1
            except Exception as e:
                print(f"Error procesando {p}: {e}")
        print(f"Procesados: {processed}")
    finally:
        conn.close()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='transparencia', help='ruta a la carpeta transparencia')
    p.add_argument('--limit', type=int, default=None, help='limitar cantidad de archivos a procesar (para pruebas)')
    args = p.parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        print('No se encontró la carpeta', root)
        return
    scan(root, args.limit)

if __name__ == '__main__':
    main()
