# 📚 GUÍA: COMPORTAMIENTO AL RE-PROCESAR PDFs

## 🔄 **¿Qué pasa al volver a ejecutar?**

### **Tanto `process_sync.py` como `tasks.py` (Celery)**:

```sql
-- Ambos usan esta misma consulta:
SELECT n.id, n.path 
FROM nodes n 
JOIN pdf_metadata p ON n.id = p.node_id 
WHERE p.ocr_status='pending'  -- ⬅️ SOLO PENDIENTES
ORDER BY n.path ASC
```

---

## 📊 **Estados y su comportamiento:**

| Estado | ¿Se re-procesa? | Notas |
|--------|-----------------|-------|
| `pending` ✅ | **SÍ** | Se procesarán normalmente |
| `done` ⏭️ | **NO** | Ya procesados, se omiten |
| `failed` ⏭️ | **NO** | Requiere acción manual |
| `processing` ⏭️ | **NO** | Se asume que está en proceso |

---

## ✅ **REGISTROS CON 'done'**

**Comportamiento**: Se **OMITEN** completamente

```
ID: 3  | done | 2009/obras/15340.PDF
ID: 4  | done | 2009/obras/15341.PDF
...
```

- ✅ Ya tienen `ocr_pdf_path`, `ocr_text`, `snippet`
- ✅ El PDF OCR ya existe en `transparencia_ocr/`
- ✅ No se volverán a procesar aunque ejecutes de nuevo
- ✅ **ESTO ES BUENO** - evita re-procesar lo ya hecho

**Para re-procesarlos (si realmente lo necesitas)**:
```sql
UPDATE pdf_metadata 
SET ocr_status='pending' 
WHERE node_id IN (3, 4, 5);  -- IDs específicos
```

---

## ❌ **REGISTROS CON 'failed'**

**Comportamiento**: Se **OMITEN** automáticamente

```
ID: 27 | failed | 2009/obras/15365.PDF
   Error: Error ocrmypdf: Tesseract warning...
```

**Para re-intentarlos**:
```powershell
# Opción 1: Usar el script helper (RECOMENDADO)
python .\proyecto\reset_failed.py --retry-failed

# Opción 2: SQL directo
# UPDATE pdf_metadata SET ocr_status='pending', last_error=NULL WHERE ocr_status='failed';
```

---

## ⏳ **REGISTROS CON 'processing'**

**Comportamiento**: Se **OMITEN** (asume que otro worker lo está procesando)

**Problema**: Si un worker se cae/cancela, quedan "atorados"

```
ID: 100 | processing | 2009/obras/12345.PDF
   Desde hace: 45 minutos
```

**Para liberarlos**:
```powershell
# Liberar los que llevan más de 30 minutos
python .\proyecto\reset_failed.py --free-stuck

# O con tiempo personalizado (ej: 60 min)
python .\proyecto\reset_failed.py --free-stuck --stuck-minutes 60
```

---

## 🛠️ **SCRIPTS DE UTILIDAD CREADOS**

### **1. `analyze_status.py`** - Ver estado detallado
```powershell
python .\proyecto\analyze_status.py
```
Muestra:
- Resumen por estado
- Primeros 60 registros
- Registros con error
- Registros atorados

### **2. `reset_failed.py`** - Gestionar problemas
```powershell
# Solo ver estadísticas
python .\proyecto\reset_failed.py --stats

# Re-intentar fallidos
python .\proyecto\reset_failed.py --retry-failed

# Liberar atorados
python .\proyecto\reset_failed.py --free-stuck

# Hacer ambas cosas
python .\proyecto\reset_failed.py --retry-failed --free-stuck
```

### **3. `check_status.py`** - Resumen rápido
```powershell
python .\proyecto\check_status.py
```

---

## 📝 **WORKFLOW RECOMENDADO**

### **Antes de procesar un nuevo lote:**

```powershell
# 1. Ver estado actual
python .\proyecto\analyze_status.py

# 2. Liberar atorados y re-intentar fallidos (si los hay)
python .\proyecto\reset_failed.py --retry-failed --free-stuck

# 3. Ver cuántos quedan pendientes
python .\proyecto\check_status.py

# 4. Procesar
# Opción A: process_sync.py
python .\proyecto\process_sync.py --root C:\xampp_php8\htdocs\OCR\transparencia --limit 100

# Opción B: Celery (más rápido)
# Terminal 1: Workers
celery -A tasks worker --loglevel=info --concurrency=7

# Terminal 2: Encolar
python .\proyecto\enqueue_pdfs.py --limit 500
```

---

## 💡 **RESPUESTAS A TU PREGUNTA**

### **"¿Qué ocurre con los que tienen error o fueron pasados por alto?"**

1. **Los que tienen 'failed'**: 
   - ✅ Se OMITEN al re-ejecutar
   - ✅ Necesitas cambiarlos a 'pending' manualmente
   - ✅ Usa: `python .\proyecto\reset_failed.py --retry-failed`

2. **Los que están 'done'**:
   - ✅ Se OMITEN (ya procesados correctamente)
   - ✅ No se vuelven a procesar
   - ✅ **Esto es correcto** - evita duplicar trabajo

3. **Los que están 'processing'**:
   - ✅ Se OMITEN (se asume que se están procesando)
   - ⚠️ Si están atorados, libéralos: `python .\proyecto\reset_failed.py --free-stuck`

4. **Los que están 'pending'**:
   - ✅ Se PROCESAN normalmente
   - ✅ Son los únicos que se toman

---

## ✅ **ESTADO ACTUAL (después de limpiar)**

```
pending:  7,824 PDFs  ← Listos para procesar
done:        59 PDFs  ← Ya procesados ✅
failed:       0 PDFs  ← Re-intentados ✅
```

---

## 🚀 **¿LISTO PARA CONTINUAR?**

Ahora que entiendes el comportamiento y has limpiado los fallidos, puedes:

1. **Procesar los 7,824 restantes con Celery (7 workers)**
   - Tiempo estimado: ~22 horas
   
2. **Procesar con process_sync.py**
   - Tiempo estimado: ~157 horas

**Los que ya están en 'done' NO se volverán a procesar** ✅
