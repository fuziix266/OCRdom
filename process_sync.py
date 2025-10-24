#!/usr/bin/env python3
"""
Procesador síncrono de OCR para pruebas rápidas.
Selecciona N PDFs con ocr_status='pending' y ejecuta ocrmypdf + pdftotext, luego
actualiza la tabla pdf_metadata en la base `ocr`.

Uso:
  python process_sync.py --root C:\ruta\a\transparencia --limit 5

Requiere: ocrmypdf, tesseract, pdftotext en PATH y conexión DB en .env
"""
import os
import subprocess
import argparse
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import pymysql
import json
try:
    from opensearchpy import OpenSearch
except Exception:
    OpenSearch = None

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

def find_pending(conn, limit=5):
    with conn.cursor() as cur:
        cur.execute("SELECT n.id as node_id, n.path as path FROM nodes n JOIN pdf_metadata p ON n.id=p.node_id WHERE p.ocr_status='pending' ORDER BY n.path ASC LIMIT %s", (limit,))
        return cur.fetchall()

def mark_processing(conn, node_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE pdf_metadata SET ocr_status='processing', ocr_started_at=NOW(), updated_at=NOW() WHERE node_id=%s", (node_id,))
    conn.commit()

def mark_failed(conn, node_id, error):
    with conn.cursor() as cur:
        cur.execute("UPDATE pdf_metadata SET ocr_status='failed', last_error=%s, updated_at=NOW() WHERE node_id=%s", (str(error), node_id))
    conn.commit()

def mark_done(conn, node_id, ocr_pdf_path, ocr_text, snippet):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE pdf_metadata SET ocr_status='done', ocr_pdf_path=%s, ocr_text=%s, snippet=%s, ocr_finished_at=NOW(), updated_at=NOW() WHERE node_id=%s",
            (ocr_pdf_path, ocr_text, snippet, node_id)
        )
    conn.commit()

def do_ocr(root, rel_path, work_dir, lang='spa'):
    src = Path(root) / Path(rel_path)
    if not src.exists():
        raise FileNotFoundError(src)
    # mirror structure under transparencia_ocr sibling to root
    root_parent = Path(root).parent
    target_base = root_parent / 'transparencia_ocr'
    target_path = target_base / Path(rel_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    out_pdf = target_path
    # ocrmypdf with cleaning (requires unpaper) and background removal
    cmd = [
        'ocrmypdf',
        '--clean',
        '--remove-background',
        '--deskew',
        '-l', lang,
        str(src),
        str(out_pdf)
    ]
    subprocess.run(cmd, check=True)
    # extract text
    txt_file = out_pdf.with_suffix('.txt')
    subprocess.run(['pdftotext', str(out_pdf), str(txt_file)], check=True)
    ocr_text = txt_file.read_text(encoding='utf-8', errors='ignore')
    snippet = (ocr_text or '')[:1000]
    return str(out_pdf), ocr_text, snippet


def index_to_opensearch(node_id, path, ocr_text):
    url = os.environ.get('OPENSEARCH_URL')
    if not url or OpenSearch is None:
        return False
    try:
        client = OpenSearch([url])
        idx = os.environ.get('OPENSEARCH_INDEX', 'ocr_documents')
        doc = {
            'node_id': node_id,
            'path': path,
            'text': ocr_text
        }
        client.index(index=idx, body=doc, id=str(node_id))
        return True
    except Exception:
        return False

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default=str(Path('..').resolve() / 'transparencia'), help='ruta a carpeta transparencia')
    p.add_argument('--limit', type=int, default=5)
    p.add_argument('--lang', default=os.environ.get('OCR_LANG', 'spa'))
    args = p.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print('Root no existe:', root)
        return

    conn = pymysql.connect(**DB_CONF)
    try:
        rows = find_pending(conn, args.limit)
        if not rows:
            print('No hay archivos pendientes.')
            return
        print(f'Procesando {len(rows)} archivos...')
        for r in rows:
            node_id = r['node_id']
            rel = r['path']
            try:
                mark_processing(conn, node_id)
                with tempfile.TemporaryDirectory() as td:
                    ocr_pdf_path, ocr_text, snippet = do_ocr(root, rel, td, args.lang)
                mark_done(conn, node_id, ocr_pdf_path, ocr_text, snippet)
                indexed = index_to_opensearch(node_id, rel, ocr_text)
                print(f'OK node={node_id} path={rel} indexed={indexed}')
            except Exception as e:
                mark_failed(conn, node_id, str(e))
                print(f'FAILED node={node_id} path={rel} error={e}')
    finally:
        conn.close()

if __name__ == '__main__':
    main()
