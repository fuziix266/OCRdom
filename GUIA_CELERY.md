# =============================================================================
# GUÍA RÁPIDA: Procesamiento OCR Masivo con Celery
# =============================================================================

## 📋 REQUISITOS PREVIOS

1. **Redis debe estar corriendo** (requerido por Celery)
   - Windows: Descargar Redis o usar Docker
   - Docker: `docker run -d -p 6379:6379 redis:latest`
   - Verificar: `redis-cli ping` debe responder `PONG`

2. **Dependencias del sistema instaladas**
   - Tesseract OCR
   - Ghostscript
   - Poppler utils (pdftotext)

3. **Dependencias Python instaladas**
   - Ver requirements.txt
   - `pip install celery[redis] pymysql pikepdf ocrmypdf python-dotenv`


## 🚀 INICIO RÁPIDO

### Paso 1: Verificar Redis
```powershell
# Si usas Docker
docker run -d -p 6379:6379 --name redis-ocr redis:latest

# Verificar conexión
redis-cli ping
```

### Paso 2: Iniciar Workers de Celery
```powershell
# Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# Opción 1: Worker simple (1 worker, 1 tarea a la vez)
cd proyecto
celery -A tasks worker --loglevel=info --concurrency=1

# Opción 2: Usar el script helper (recomendado)
python .\proyecto\start_workers.py --workers 4 --concurrency 1

# Opción 3: Múltiples workers en background
python .\proyecto\start_workers.py --workers 4
```

### Paso 3: Encolar PDFs para Procesamiento
```powershell
# Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# Encolar todos los PDFs pendientes
python .\proyecto\enqueue_pdfs.py

# Encolar solo 100 PDFs (para prueba)
python .\proyecto\enqueue_pdfs.py --limit 100

# Especificar ruta diferente
python .\proyecto\enqueue_pdfs.py --root C:\ruta\a\transparencia --limit 500
```

### Paso 4: Monitorear el Progreso
```powershell
# Ver estado de la base de datos
python .\proyecto\check_status.py

# Ver tareas activas en Celery
celery -A tasks inspect active

# Ver estadísticas de workers
celery -A tasks inspect stats

# Ver tareas en cola
celery -A tasks inspect reserved
```


## ⚙️ CONFIGURACIÓN

### Variables de Entorno (.env)
```ini
# Base de datos
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASS=
DB_NAME=ocr

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# OCR Settings
OCR_LANG=spa
OCR_TIMEOUT=600
OCR_SOFT_TIMEOUT=600
OCR_HARD_TIMEOUT=900

# Workers
WORKER_PREFETCH=1

# Transparencia root (opcional)
TRANSPARENCIA_ROOT=C:\xampp_php8\htdocs\OCR\transparencia
```


## 📊 ESTRATEGIAS DE PROCESAMIENTO

### Para Pocos Archivos (<100):
```powershell
# Usar process_sync.py (más simple)
python .\proyecto\process_sync.py --root C:\path\to\transparencia --limit 50
```

### Para Miles de Archivos:
```powershell
# 1. Iniciar Redis
docker start redis-ocr

# 2. Iniciar 4 workers (procesa 4 PDFs en paralelo)
python .\proyecto\start_workers.py --workers 4 --concurrency 1

# 3. En otra terminal, encolar todos los PDFs
python .\proyecto\enqueue_pdfs.py

# 4. Monitorear progreso
python .\proyecto\check_status.py
```


## 🔧 CONFIGURACIÓN AVANZADA

### Workers según CPU disponible:
- **CPU 4 cores**: --workers 2 --concurrency 1
- **CPU 8 cores**: --workers 4 --concurrency 1
- **CPU 16 cores**: --workers 8 --concurrency 1

### Ajustar timeouts según complejidad de PDFs:
- PDFs simples (2-5 páginas): OCR_TIMEOUT=300 (5 min)
- PDFs complejos (10+ páginas): OCR_TIMEOUT=900 (15 min)


## 🛑 DETENER PROCESAMIENTO

### Detener workers gracefully:
```powershell
# Ctrl+C en la terminal donde corren los workers
```

### Limpiar cola (vaciar tareas pendientes):
```powershell
celery -A tasks purge
```

### Reiniciar todo:
```powershell
# 1. Detener workers (Ctrl+C)
# 2. Limpiar cola
celery -A tasks purge
# 3. Reiniciar workers
python .\proyecto\start_workers.py --workers 4
```


## 📈 OPTIMIZACIÓN

### Ajuste fino de workers:
```python
# En tasks.py, ya configurado:
worker_prefetch_multiplier=1  # Un worker toma 1 tarea a la vez
task_acks_late=True           # Confirma solo cuando termine
task_reject_on_worker_lost=True  # Re-encola si worker muere
```

### Monitoreo en tiempo real:
```powershell
# Instalar flower (opcional)
pip install flower
celery -A tasks flower

# Abrir http://localhost:5555 en el navegador
```


## 🐛 TROUBLESHOOTING

### "Error: No puedo conectar a Redis"
- Verificar que Redis esté corriendo: `redis-cli ping`
- Verificar REDIS_URL en .env

### "Workers no procesan tareas"
- Verificar que workers estén corriendo: `celery -A tasks inspect active`
- Verificar logs de workers en logs/

### "PDFs muy grandes causan timeouts"
- Aumentar OCR_TIMEOUT en .env
- Reducir --concurrency a 1

### "Error: FileNotFoundError"
- Verificar que la ruta en enqueue_pdfs.py sea correcta
- Verificar permisos de lectura en transparencia/


## 📁 ESTRUCTURA DE SALIDA

```
transparencia/              # PDFs originales
└── 2024/
    └── certificados/
        └── documento.pdf

transparencia_ocr/          # PDFs con OCR (espejo)
└── 2024/
    └── certificados/
        └── documento.pdf   # PDF con capa OCR
```


## ✅ VERIFICACIÓN FINAL

```powershell
# 1. Redis corriendo
redis-cli ping  # → PONG

# 2. Workers activos
celery -A tasks inspect active  # → Lista de workers

# 3. Estado de DB
python .\proyecto\check_status.py  # → pending, processing, done

# 4. Archivos generados
ls transparencia_ocr\  # → Archivos OCR
```

---

**¡Listo para procesar miles de PDFs en paralelo! 🚀**
