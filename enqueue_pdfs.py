#!/usr/bin/env python3
r"""
Script para encolar PDFs pendientes en Celery para procesamiento OCR masivo.

Uso:
    # Encolar todos los PDFs pendientes
    python enqueue_pdfs.py
    
    # Encolar solo 100 PDFs
    python enqueue_pdfs.py --limit 100
    
    # Especificar ruta raíz
    python enqueue_pdfs.py --root C:\xampp_php8\htdocs\OCR\transparencia --limit 500
"""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
import pymysql

load_dotenv()

# Importar la tarea de Celery
from tasks import process_pdf

DB_CONF = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', 'ocr'),
    'autocommit': False,
    'cursorclass': pymysql.cursors.DictCursor,
}

def enqueue_pending(root, limit=None):
    """Encola PDFs pendientes en Celery"""
    conn = pymysql.connect(**DB_CONF)
    try:
        with conn.cursor() as cur:
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
            
            print(f"\n📊 Encontrados {len(rows)} PDFs pendientes")
            
            if not rows:
                print("✅ No hay PDFs pendientes para procesar")
                return
            
            print(f"🚀 Encolando {len(rows)} tareas en Celery...\n")
            
            enqueued = 0
            skipped = 0
            
            for i, row in enumerate(rows, 1):
                node_id = row['node_id']
                rel_path = row['path']
                pdf_path = Path(root) / rel_path
                
                if pdf_path.exists():
                    # Encolar tarea en Celery
                    task = process_pdf.delay(node_id, str(pdf_path))
                    enqueued += 1
                    if i % 50 == 0:
                        print(f"  ✓ Encoladas {i}/{len(rows)} tareas...")
                else:
                    skipped += 1
                    print(f"  ⚠ Archivo no encontrado: {pdf_path}")
            
            print(f"\n{'='*60}")
            print(f"✅ Resumen:")
            print(f"   - Total procesados:  {len(rows)}")
            print(f"   - Encolados:         {enqueued}")
            print(f"   - Omitidos:          {skipped}")
            print(f"{'='*60}\n")
            print("💡 Las tareas están en cola. Asegúrate de tener workers corriendo:")
            print("   python start_workers.py --workers 4")
            print("\n📊 Para monitorear el progreso:")
            print("   celery -A tasks inspect active")
            print("   python check_status.py")
            
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Encolar PDFs pendientes para OCR con Celery')
    parser.add_argument('--root', default='C:\\xampp_php8\\htdocs\\OCR\\transparencia', 
                        help='Ruta a la carpeta transparencia')
    parser.add_argument('--limit', type=int, default=None, 
                        help='Límite de PDFs a encolar (default: todos)')
    args = parser.parse_args()
    
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"❌ Error: La ruta {root} no existe")
        return
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║           Encolar PDFs para Procesamiento OCR             ║
╠═══════════════════════════════════════════════════════════╣
║  Root:          {str(root)[:40]:<40}  ║
║  Límite:        {str(args.limit or 'Sin límite'):<40}  ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    try:
        enqueue_pending(root, args.limit)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
