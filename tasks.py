"""
Celery tasks for processing OCR of PDFs using ocrmypdf + tesseract.
Requires system dependencies: tesseract, ghostscript, poppler-utils (pdftotext).

Configuración mediante variables de entorno (ver README):
  REDIS_URL, DB_* env vars
  
Optimizado para procesamiento masivo paralelo con almacenamiento 
persistente en transparencia_ocr/ (estructura espejo).
"""
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import pymysql

load_dotenv()

from celery import Celery

REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
app = Celery('ocr_tasks', broker=REDIS_URL, backend=REDIS_URL)

# Configuración optimizada de Celery para procesamiento masivo
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=int(os.environ.get('WORKER_PREFETCH', 1)),
    task_soft_time_limit=int(os.environ.get('OCR_SOFT_TIMEOUT', 600)),
    task_time_limit=int(os.environ.get('OCR_HARD_TIMEOUT', 900)),
    result_expires=3600,
)

DB_CONF = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'ocr'),
    'autocommit': False,
    'cursorclass': pymysql.cursors.DictCursor,
}


@app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_pdf(self, node_id, pdf_path, root_path=None):
    """
    Realiza OCR sobre el PDF en pdf_path y actualiza MariaDB.
    
    Args:
        node_id: id en la tabla nodes
        pdf_path: ruta absoluta al PDF a procesar
        root_path: ruta raíz de transparencia (opcional, se detecta automáticamente)
    
    Returns:
        dict: {'status': 'done'|'failed', 'node_id': int, 'ocr_pdf_path': str}
    """
    conn = pymysql.connect(**DB_CONF)
    
    try:
        # Marcar como processing
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pdf_metadata SET ocr_status='processing', ocr_started_at=NOW(), updated_at=NOW() WHERE node_id=%s", 
                (node_id,)
            )
            conn.commit()

        # Preparar rutas de salida siguiendo la lógica de process_sync.py
        src = Path(pdf_path)
        if not src.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        # Detectar estructura y crear ruta espejo en transparencia_ocr
        parts = src.parts
        if 'transparencia' in parts:
            idx = parts.index('transparencia')
            root_parent = Path(*parts[:idx]) if parts[:idx] else Path(src.anchor)
            rel = Path(*parts[idx+1:])  # ruta relativa dentro de transparencia
            target_base = root_parent / 'transparencia_ocr'
            target_path = target_base / rel
        else:
            # Fallback si no se encuentra 'transparencia' en el path
            raise ValueError(f"No se encontró 'transparencia' en la ruta: {pdf_path}")
        
        # Crear directorio de destino
        target_path.parent.mkdir(parents=True, exist_ok=True)
        out_pdf = target_path

        # Ejecutar ocrmypdf con las mismas opciones que process_sync.py
        cmd = [
            'ocrmypdf',
            '--clean',
            '--remove-background',
            '--deskew',
            '-l', os.environ.get('OCR_LANG', 'spa'),
            str(src),
            str(out_pdf)
        ]
        
        try:
            subprocess.run(
                cmd, 
                check=True, 
                timeout=int(os.environ.get('OCR_TIMEOUT', 600)),
                capture_output=True,
                text=True
            )
        except subprocess.TimeoutExpired as e:
            error_msg = f"Timeout procesando PDF (>{os.environ.get('OCR_TIMEOUT', 600)}s)"
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pdf_metadata SET ocr_status='failed', last_error=%s, updated_at=NOW() WHERE node_id=%s",
                    (error_msg, node_id)
                )
                conn.commit()
            return {'status': 'failed', 'node_id': node_id, 'error': error_msg}
        except subprocess.CalledProcessError as e:
            error_msg = f"Error ocrmypdf: {e.stderr if e.stderr else str(e)}"
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pdf_metadata SET ocr_status='failed', last_error=%s, updated_at=NOW() WHERE node_id=%s",
                    (error_msg[:500], node_id)  # Limitar longitud del error
                )
                conn.commit()
            return {'status': 'failed', 'node_id': node_id, 'error': error_msg}

        # Extraer texto con pdftotext
        txt_file = out_pdf.with_suffix('.txt')
        try:
            subprocess.run(['pdftotext', str(out_pdf), str(txt_file)], check=True)
            ocr_text = txt_file.read_text(encoding='utf-8', errors='ignore')
            # Limpiar archivo temporal de texto
            txt_file.unlink(missing_ok=True)
        except Exception as e:
            # Si falla pdftotext, continuar sin texto (mejor tener el PDF que nada)
            ocr_text = None

        snippet = (ocr_text or '')[:1000]

        # Actualizar DB con resultado exitoso
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE pdf_metadata 
                   SET ocr_status='done', 
                       ocr_pdf_path=%s, 
                       ocr_text=%s, 
                       snippet=%s, 
                       ocr_finished_at=NOW(), 
                       updated_at=NOW() 
                   WHERE node_id=%s""",
                (str(out_pdf), ocr_text, snippet, node_id)
            )
            conn.commit()

        return {
            'status': 'done', 
            'node_id': node_id, 
            'ocr_pdf_path': str(out_pdf),
            'text_length': len(ocr_text) if ocr_text else 0
        }

    except Exception as e:
        # Capturar cualquier otro error no manejado
        error_msg = f"Error inesperado: {str(e)}"
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE pdf_metadata SET ocr_status='failed', last_error=%s, updated_at=NOW() WHERE node_id=%s",
                    (error_msg[:500], node_id)
                )
                conn.commit()
        except:
            pass  # Si falla la actualización, al menos lanzar el error original
        
        raise  # Re-lanzar para que Celery maneje el retry
    
    finally:
        conn.close()


@app.task
def enqueue_pending_pdfs(limit=None, batch_size=100):
    """
    Encola PDFs pendientes para procesamiento.
    
    Args:
        limit: número máximo de PDFs a encolar (None = todos)
        batch_size: tamaño del lote para consulta a DB
    
    Returns:
        dict: estadísticas de PDFs encolados
    """
    conn = pymysql.connect(**DB_CONF)
    try:
        with conn.cursor() as cur:
            # Obtener root path de transparencia desde las variables de entorno
            root = os.environ.get('TRANSPARENCIA_ROOT', 'C:\\xampp_php8\\htdocs\\OCR\\transparencia')
            
            # Consultar PDFs pendientes
            query = """
                SELECT n.id as node_id, n.path 
                FROM nodes n 
                JOIN pdf_metadata p ON n.id = p.node_id 
                WHERE p.ocr_status='pending' 
                ORDER BY n.path ASC
            """
            if limit:
                query += f" LIMIT {limit}"
            
            cur.execute(query)
            rows = cur.fetchall()
            
            enqueued = 0
            for row in rows:
                node_id = row['node_id']
                rel_path = row['path']
                pdf_path = Path(root) / rel_path
                
                if pdf_path.exists():
                    # Encolar tarea
                    process_pdf.delay(node_id, str(pdf_path))
                    enqueued += 1
            
            return {
                'total_pending': len(rows),
                'enqueued': enqueued,
                'skipped': len(rows) - enqueued
            }
    finally:
        conn.close()

