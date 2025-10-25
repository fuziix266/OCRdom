#!/usr/bin/env python3
"""
Script para analizar el estado de procesamiento y detectar problemas.
"""
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
        print("\n" + "="*80)
        print("  ANÁLISIS DETALLADO DEL ESTADO DE PROCESAMIENTO")
        print("="*80)
        
        # Resumen general
        with conn.cursor() as cur:
            cur.execute("SELECT ocr_status, COUNT(*) as cnt FROM pdf_metadata GROUP BY ocr_status")
            rows = cur.fetchall()
            print("\n📊 RESUMEN GENERAL:")
            for r in rows:
                print(f"   {r['ocr_status']:12}: {r['cnt']:6} registros")
        
        # Primeros 60 registros
        with conn.cursor() as cur:
            cur.execute("""
                SELECT n.id, n.path, p.ocr_status, p.last_error 
                FROM nodes n 
                JOIN pdf_metadata p ON n.id=p.node_id 
                ORDER BY n.id 
                LIMIT 60
            """)
            rows = cur.fetchall()
            
            print(f"\n📋 PRIMEROS 60 REGISTROS:")
            print("-"*80)
            for r in rows:
                error = r['last_error'][:40] if r['last_error'] else '-'
                print(f"ID: {r['id']:4} | {r['ocr_status']:12} | {r['path']:45} | {error}")
        
        # Registros con error
        with conn.cursor() as cur:
            cur.execute("""
                SELECT n.id, n.path, p.last_error 
                FROM nodes n 
                JOIN pdf_metadata p ON n.id=p.node_id 
                WHERE p.ocr_status='failed'
                LIMIT 10
            """)
            rows = cur.fetchall()
            
            if rows:
                print(f"\n❌ REGISTROS CON ERROR (primeros 10):")
                print("-"*80)
                for r in rows:
                    print(f"\nID: {r['id']} | {r['path']}")
                    print(f"   Error: {r['last_error'][:200] if r['last_error'] else 'Sin mensaje'}")
        
        # Registros en processing (posibles atorados)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT n.id, n.path, p.ocr_started_at, 
                       TIMESTAMPDIFF(MINUTE, p.ocr_started_at, NOW()) as minutos_transcurridos
                FROM nodes n 
                JOIN pdf_metadata p ON n.id=p.node_id 
                WHERE p.ocr_status='processing'
            """)
            rows = cur.fetchall()
            
            if rows:
                print(f"\n⏳ REGISTROS EN PROCESSING (posibles atorados):")
                print("-"*80)
                for r in rows:
                    print(f"ID: {r['id']:4} | {r['path']:45} | Hace {r['minutos_transcurridos']} minutos")
        
        # Explicación sobre comportamiento
        print("\n" + "="*80)
        print("  COMPORTAMIENTO AL RE-PROCESAR")
        print("="*80)
        print("""
📝 ¿Qué pasa al volver a ejecutar process_sync.py o encolar con Celery?

1️⃣  REGISTROS CON 'pending':
   ✅ Se procesarán normalmente
   ✅ Tanto process_sync.py como tasks.py seleccionan solo 'pending'
   
2️⃣  REGISTROS CON 'done':
   ⏭️  Se OMITEN (no se re-procesan)
   ℹ️  Ya tienen ocr_pdf_path, ocr_text, etc.
   
3️⃣  REGISTROS CON 'failed':
   ⏭️  Se OMITEN (no se re-intentan automáticamente)
   ⚠️  Necesitas cambiarlos manualmente a 'pending' para re-intentar
   
4️⃣  REGISTROS CON 'processing':
   ⏭️  Se OMITEN (se asume que otro worker los está procesando)
   ⚠️  Si están "atorados", necesitas cambiarlos a 'pending' manualmente

💡 COMANDOS ÚTILES:

   # Re-intentar todos los que fallaron
   UPDATE pdf_metadata SET ocr_status='pending', last_error=NULL 
   WHERE ocr_status='failed';
   
   # Liberar los atorados en processing (más de 30 min)
   UPDATE pdf_metadata SET ocr_status='pending' 
   WHERE ocr_status='processing' 
   AND TIMESTAMPDIFF(MINUTE, ocr_started_at, NOW()) > 30;
   
   # Ver cuántos hay de cada tipo
   SELECT ocr_status, COUNT(*) FROM pdf_metadata GROUP BY ocr_status;
        """)
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
