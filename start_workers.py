#!/usr/bin/env python3
"""
Script para iniciar workers de Celery para procesamiento OCR masivo.

Uso básico:
    python start_workers.py --workers 4

Uso avanzado:
    python start_workers.py --workers 4 --concurrency 2 --loglevel info

El script puede:
- Iniciar múltiples workers en paralelo
- Configurar concurrencia por worker
- Gestionar logs
"""
import argparse
import os
import sys
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Iniciar workers de Celery para OCR')
    parser.add_argument('--workers', type=int, default=1, help='Número de workers a iniciar (default: 1)')
    parser.add_argument('--concurrency', type=int, default=1, help='Tareas concurrentes por worker (default: 1)')
    parser.add_argument('--loglevel', default='info', choices=['debug', 'info', 'warning', 'error'], help='Nivel de log')
    parser.add_argument('--queue', default='ocr', help='Nombre de la cola (default: ocr)')
    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║         Iniciando Workers de Celery para OCR              ║
╠═══════════════════════════════════════════════════════════╣
║  Workers:       {args.workers:<5}                                      ║
║  Concurrency:   {args.concurrency:<5} (tareas por worker)               ║
║  Log level:     {args.loglevel:<10}                               ║
║  Queue:         {args.queue:<10}                               ║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Verificar que existe tasks.py
    tasks_file = Path(__file__).parent / 'tasks.py'
    if not tasks_file.exists():
        print(f"❌ Error: No se encontró tasks.py en {tasks_file}")
        sys.exit(1)

    # Crear directorio de logs si no existe
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    if args.workers == 1:
        # Modo simple: un solo worker
        print("\n🚀 Iniciando worker único...\n")
        cmd = [
            'celery',
            '-A', 'tasks',
            'worker',
            '--loglevel', args.loglevel,
            '--concurrency', str(args.concurrency),
            '--prefetch-multiplier', '1',
            '-Q', args.queue,
        ]
        
        try:
            subprocess.run(cmd, cwd=Path(__file__).parent)
        except KeyboardInterrupt:
            print("\n\n👋 Worker detenido por el usuario")
    else:
        # Modo múltiple: varios workers
        print(f"\n🚀 Iniciando {args.workers} workers en background...\n")
        processes = []
        
        for i in range(args.workers):
            worker_name = f"ocr_worker_{i+1}"
            log_file = log_dir / f"{worker_name}.log"
            
            cmd = [
                'celery',
                '-A', 'tasks',
                'worker',
                '--loglevel', args.loglevel,
                '--concurrency', str(args.concurrency),
                '--prefetch-multiplier', '1',
                '-n', worker_name,
                '-Q', args.queue,
                '--logfile', str(log_file),
            ]
            
            print(f"  ▶ Iniciando {worker_name} (log: {log_file})")
            proc = subprocess.Popen(cmd, cwd=Path(__file__).parent)
            processes.append((worker_name, proc))
        
        print(f"\n✅ {args.workers} workers iniciados!")
        print("\nPara detenerlos:")
        print("  - En Windows: Ctrl+C o buscar procesos celery en el Administrador de Tareas")
        print("  - En Linux/Mac: pkill -f 'celery worker'")
        print("\nPara monitorear: celery -A tasks inspect active")
        print(f"Logs disponibles en: {log_dir}\n")
        
        try:
            # Esperar a que terminen (o Ctrl+C)
            for name, proc in processes:
                proc.wait()
        except KeyboardInterrupt:
            print("\n\n⏹ Deteniendo workers...")
            for name, proc in processes:
                proc.terminate()
            print("👋 Workers detenidos")

if __name__ == '__main__':
    main()
