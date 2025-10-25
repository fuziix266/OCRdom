#!/usr/bin/env python3
"""
Script para gestionar registros con problemas (failed, processing atorados).

Uso:
    # Re-intentar todos los fallidos
    python reset_failed.py --retry-failed
    
    # Liberar atorados en processing
    python reset_failed.py --free-stuck
    
    # Hacer ambas cosas
    python reset_failed.py --retry-failed --free-stuck
    
    # Solo ver estadísticas
    python reset_failed.py --stats
"""
import argparse
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

def show_stats(conn):
    """Muestra estadísticas actuales"""
    print("\n" + "="*70)
    print("  ESTADÍSTICAS ACTUALES")
    print("="*70)
    
    with conn.cursor() as cur:
        cur.execute("SELECT ocr_status, COUNT(*) as cnt FROM pdf_metadata GROUP BY ocr_status")
        rows = cur.fetchall()
        print("\n📊 Por estado:")
        for r in rows:
            print(f"   {r['ocr_status']:12}: {r['cnt']:6} registros")
    
    # Atorados en processing
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as cnt 
            FROM pdf_metadata 
            WHERE ocr_status='processing' 
            AND TIMESTAMPDIFF(MINUTE, ocr_started_at, NOW()) > 30
        """)
        stuck = cur.fetchone()['cnt']
        if stuck > 0:
            print(f"\n⚠️  {stuck} registros atorados en 'processing' (>30 min)")

def retry_failed(conn):
    """Reintentar todos los registros fallidos"""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM pdf_metadata WHERE ocr_status='failed'")
        count = cur.fetchone()['cnt']
        
        if count == 0:
            print("\n✅ No hay registros fallidos para re-intentar")
            return
        
        print(f"\n🔄 Re-intentando {count} registros fallidos...")
        cur.execute("""
            UPDATE pdf_metadata 
            SET ocr_status='pending', 
                last_error=NULL,
                updated_at=NOW()
            WHERE ocr_status='failed'
        """)
        conn.commit()
        print(f"✅ {count} registros cambiados a 'pending'")

def free_stuck(conn, minutes=30):
    """Liberar registros atorados en processing"""
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) as cnt 
            FROM pdf_metadata 
            WHERE ocr_status='processing' 
            AND TIMESTAMPDIFF(MINUTE, ocr_started_at, NOW()) > {minutes}
        """)
        count = cur.fetchone()['cnt']
        
        if count == 0:
            print(f"\n✅ No hay registros atorados en 'processing' (>{minutes} min)")
            return
        
        print(f"\n🔓 Liberando {count} registros atorados (>{minutes} min)...")
        cur.execute(f"""
            UPDATE pdf_metadata 
            SET ocr_status='pending',
                updated_at=NOW()
            WHERE ocr_status='processing' 
            AND TIMESTAMPDIFF(MINUTE, ocr_started_at, NOW()) > {minutes}
        """)
        conn.commit()
        print(f"✅ {count} registros cambiados a 'pending'")

def main():
    parser = argparse.ArgumentParser(description='Gestionar registros con problemas')
    parser.add_argument('--retry-failed', action='store_true', 
                        help='Re-intentar todos los registros fallidos')
    parser.add_argument('--free-stuck', action='store_true', 
                        help='Liberar registros atorados en processing')
    parser.add_argument('--stuck-minutes', type=int, default=30,
                        help='Minutos para considerar un registro como atorado (default: 30)')
    parser.add_argument('--stats', action='store_true',
                        help='Solo mostrar estadísticas')
    args = parser.parse_args()
    
    # Si no se especifica nada, mostrar estadísticas
    if not (args.retry_failed or args.free_stuck or args.stats):
        args.stats = True
    
    conn = pymysql.connect(**DB_CONF)
    try:
        show_stats(conn)
        
        if args.retry_failed:
            retry_failed(conn)
        
        if args.free_stuck:
            free_stuck(conn, args.stuck_minutes)
        
        if args.retry_failed or args.free_stuck:
            print("\n" + "="*70)
            print("  ESTADÍSTICAS DESPUÉS DE LOS CAMBIOS")
            print("="*70)
            show_stats(conn)
        
        print("\n" + "="*70)
        print("✅ Listo para procesar:")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM pdf_metadata WHERE ocr_status='pending'")
            pending = cur.fetchone()['cnt']
            print(f"   {pending} PDFs pendientes de procesar")
        print("="*70 + "\n")
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
