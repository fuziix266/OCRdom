"""
Celery tasks for processing OCR of PDFs using ocrmypdf + tesseract.
Requires system dependencies: tesseract, ghostscript, poppler-utils (pdftotext).

Configuración mediante variables de entorno (ver README):
  REDIS_URL, DB_* env vars
"""
import os
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import pymysql

load_dotenv()

from celery import Celery

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('ocr_tasks', broker=REDIS_URL)

DB_CONF = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'transparencia'),
    'autocommit': False,
    'cursorclass': pymysql.cursors.DictCursor,
}

@app.task(bind=True, acks_late=True)
def process_pdf(self, node_id, pdf_path):
    """Realiza OCR sobre el PDF en pdf_path y actualiza MariaDB.
    node_id: id en la tabla nodes
    pdf_path: ruta absoluta al PDF a procesar (si el scanner administra rutas relativas, resolvéralas antes)
    """
    conn = pymysql.connect(**DB_CONF)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE pdf_metadata SET ocr_status='processing', ocr_started_at=NOW() WHERE node_id=%s", (node_id,))
            conn.commit()

        # crear archivo output temporal
        out_pdf = Path(tempfile.mkdtemp()) / (Path(pdf_path).stem + '_ocr.pdf')

        cmd = [
            'ocrmypdf',
            '--deskew',
            '--clean',
            '--remove-background',
            '-l', os.environ.get('OCR_LANG', 'spa'),
            pdf_path,
            str(out_pdf)
        ]
        try:
            subprocess.run(cmd, check=True, timeout=int(os.environ.get('OCR_TIMEOUT', 300)))
        except subprocess.CalledProcessError as e:
            with conn.cursor() as cur:
                cur.execute("UPDATE pdf_metadata SET ocr_status='failed', last_error=%s, updated_at=NOW() WHERE node_id=%s", (str(e), node_id))
                conn.commit()
            return {'status': 'failed', 'error': str(e)}

        # extraer texto con pdftotext (poppler) para guardar en DB o indexar
        txt_file = out_pdf.with_suffix('.txt')
        try:
            subprocess.run(['pdftotext', str(out_pdf), str(txt_file)], check=True)
            ocr_text = txt_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            ocr_text = None

        snippet = (ocr_text or '')[:1000]

        # actualizar DB: guardar ruta del pdf OCR y texto
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pdf_metadata SET ocr_status='done', ocr_pdf_path=%s, ocr_text=%s, snippet=%s, ocr_finished_at=NOW(), updated_at=NOW() WHERE node_id=%s",
                (str(out_pdf), ocr_text, snippet, node_id)
            )
            conn.commit()

        # TODO: indexar ocr_text en OpenSearch si está disponible
        return {'status': 'done', 'node_id': node_id}
    finally:
        conn.close()
