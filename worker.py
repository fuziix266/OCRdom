"""Helper to run a Celery worker for OCR tasks.

Uso:
  celery -A tasks worker --loglevel=info

También se incluye este script para lanzar el worker desde Python si se desea.
"""
import os
import sys

if __name__ == '__main__':
    # Recomendación: lanzar via CLI: celery -A tasks worker --loglevel=info
    print("Ejecuta: celery -A tasks worker --loglevel=info")
    sys.exit(0)
