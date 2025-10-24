# OCR pipeline — proyecto

Este repositorio contiene scripts y esquema para:

- Recorrer la carpeta `transparencia/` y almacenar metadatos en MariaDB.
- Worker que procesa PDFs con `ocrmypdf` + `tesseract` y guarda texto en la base.
- `docker-compose.yml` con MariaDB, Redis y OpenSearch para pruebas locales.

Requisitos del sistema (debes instalarlos en tu host):

- Python 3.9+
- tesseract (v4/5) con modelos de idioma (ej. `spa`)
- ghostscript
- poppler-utils (pdftotext)
- ocrmypdf (usa Ghostscript y Tesseract)

En Windows usar Chocolatey o instaladores oficiales para Tesseract/Ghostscript/Poppler.

Instalación de dependencias Python (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Levantar servicios con Docker Compose (local):

```powershell
docker compose up -d
```

Variables de entorno (ejemplo `.env`):

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=appuser
DB_PASS=apppassword
DB_NAME=transparencia
REDIS_URL=redis://127.0.0.1:6379/0
OCR_LANG=spa
```

Uso — preparar esquema:

1. Conecta a MariaDB (usuario root) y crea la base `transparencia` o usa la que crea el compose.
2. Ejecuta el script SQL `mariadb_schema.sql` en la base.

Scanner (poblar DB con PDFs):

```powershell
python .\scan_transparencia.py --root C:\ruta\a\transparencia
```

Iniciar worker (celery) — desde el entorno virtual:

```powershell
# lanzar worker
celery -A tasks worker --loglevel=info
```

Enviar tarea manualmente (ejemplo desde Python REPL):

```python
from tasks import process_pdf
process_pdf.delay(123, 'C:/ruta/a/transparencia/2009/obras/1234.pdf')
```

Notas:

- `ocrmypdf` debe estar disponible en PATH (instalación del sistema). En servidores Linux instalar paquetes del sistema.
- El ejemplo del worker guarda el PDF OCRizado en un directorio temporal. En producción, guarda en almacenamiento permanente (S3/MinIO o en disco) y actualiza `ocr_pdf_path`.
- Para búsqueda avanzada configura OpenSearch y añade indexación en `tasks.process_pdf`.

Limitaciones de este scaffold:

- No se incluye gestión completa de `parent_id` para nodos de carpetas; es sencillo extender `scan_transparencia.py` para crear nodos de carpeta.
- No hay autenticación/ACL ni backups automatizados — planificar para producción.
