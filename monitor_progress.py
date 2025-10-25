#!/usr/bin/env python3
"""
Script para monitorear el progreso del procesamiento OCR en tiempo real.

Uso:
    python monitor_progress.py
    
    # Actualizar cada 30 segundos
    python monitor_progress.py --interval 30
"""
import argparse
import os
import time
from datetime import datetime, timedelta
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

def clear_screen():
    """Limpia la pantalla"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_stats(conn):
    """Obtiene estadísticas actuales"""
    with conn.cursor() as cur:
        cur.execute("SELECT ocr_status, COUNT(*) as cnt FROM pdf_metadata GROUP BY ocr_status")
        rows = cur.fetchall()
        stats = {r['ocr_status']: r['cnt'] for r in rows}
        
        # Obtener total
        cur.execute("SELECT COUNT(*) as total FROM pdf_metadata")
        total = cur.fetchone()['total']
        
        return stats, total

def calculate_eta(done, total, start_time, elapsed_seconds):
    """Calcula tiempo estimado de finalización"""
    if done == 0:
        return None, None
    
    rate = done / elapsed_seconds if elapsed_seconds > 0 else 0  # PDFs por segundo
    remaining = total - done
    
    if rate == 0:
        return None, None
    
    eta_seconds = remaining / rate
    eta_time = datetime.now() + timedelta(seconds=eta_seconds)
    
    return eta_time, rate * 3600  # PDFs por hora

def format_time(seconds):
    """Formatea segundos a HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def monitor(interval=10):
    """Monitorea el progreso continuamente"""
    conn = pymysql.connect(**DB_CONF)
    start_time = time.time()
    last_done = 0
    
    try:
        print("\n🚀 Iniciando monitoreo del procesamiento OCR...")
        print("Presiona Ctrl+C para detener\n")
        time.sleep(2)
        
        while True:
            clear_screen()
            
            stats, total = get_stats(conn)
            pending = stats.get('pending', 0)
            done = stats.get('done', 0)
            failed = stats.get('failed', 0)
            processing = stats.get('processing', 0)
            
            elapsed = time.time() - start_time
            progress_pct = (done / total * 100) if total > 0 else 0
            
            # Calcular velocidad instantánea
            instant_rate = (done - last_done) / interval if interval > 0 else 0
            instant_rate_hour = instant_rate * 3600
            
            # Calcular ETA
            eta_time, avg_rate = calculate_eta(done, total, start_time, elapsed)
            
            print("="*80)
            print(f"  MONITOR DE PROCESAMIENTO OCR - {datetime.now().strftime('%H:%M:%S')}")
            print("="*80)
            
            print(f"\n📊 PROGRESO GENERAL:")
            print(f"   Total PDFs:        {total:,}")
            print(f"   Procesados:        {done:,} ({progress_pct:.1f}%)")
            print(f"   Pendientes:        {pending:,}")
            print(f"   En proceso:        {processing}")
            print(f"   Fallidos:          {failed}")
            
            # Barra de progreso
            bar_width = 50
            filled = int(bar_width * progress_pct / 100)
            bar = '█' * filled + '░' * (bar_width - filled)
            print(f"\n   [{bar}] {progress_pct:.1f}%")
            
            print(f"\n⏱️  TIEMPO:")
            print(f"   Transcurrido:      {format_time(elapsed)}")
            if eta_time:
                remaining_seconds = (eta_time - datetime.now()).total_seconds()
                print(f"   Restante (est):    {format_time(remaining_seconds)}")
                print(f"   ETA:               {eta_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            print(f"\n⚡ VELOCIDAD:")
            if avg_rate:
                print(f"   Promedio:          {avg_rate:.1f} PDFs/hora")
            print(f"   Actual:            {instant_rate_hour:.1f} PDFs/hora")
            
            if failed > 0:
                print(f"\n⚠️  ADVERTENCIA: {failed} PDFs fallaron")
                print(f"   Usa: python reset_failed.py --retry-failed para re-intentar")
            
            print("\n" + "="*80)
            print(f"  Actualizando en {interval} segundos... (Ctrl+C para detener)")
            print("="*80)
            
            last_done = done
            
            # Verificar si terminó
            if pending == 0 and processing == 0:
                print("\n\n🎉 ¡PROCESAMIENTO COMPLETADO!")
                print(f"   Total procesados: {done:,}/{total:,}")
                print(f"   Tiempo total: {format_time(elapsed)}")
                if failed > 0:
                    print(f"   ⚠️  {failed} PDFs fallaron")
                break
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoreo detenido por el usuario")
        stats, total = get_stats(conn)
        done = stats.get('done', 0)
        print(f"\n📊 Estado final:")
        print(f"   Procesados: {done:,}/{total:,} ({done/total*100:.1f}%)")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Monitorear progreso de OCR')
    parser.add_argument('--interval', type=int, default=10,
                        help='Intervalo de actualización en segundos (default: 10)')
    args = parser.parse_args()
    
    monitor(args.interval)

if __name__ == '__main__':
    main()
