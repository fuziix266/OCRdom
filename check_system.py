#!/usr/bin/env python3
"""
Script para analizar el sistema y recomendar configuración óptima de workers.

Analiza:
- CPU cores disponibles
- Memoria RAM
- Espacio en disco
- Recomienda número de workers
"""
import os
import sys
import platform
import psutil
from pathlib import Path

def get_system_info():
    """Obtiene información del sistema"""
    info = {}
    
    # CPU
    info['cpu_count_logical'] = psutil.cpu_count(logical=True)  # Hilos
    info['cpu_count_physical'] = psutil.cpu_count(logical=False)  # Cores físicos
    info['cpu_percent'] = psutil.cpu_percent(interval=1)
    info['cpu_freq'] = psutil.cpu_freq()
    
    # Memoria
    mem = psutil.virtual_memory()
    info['ram_total_gb'] = mem.total / (1024**3)
    info['ram_available_gb'] = mem.available / (1024**3)
    info['ram_percent'] = mem.percent
    
    # Disco
    disk = psutil.disk_usage('C:\\')
    info['disk_total_gb'] = disk.total / (1024**3)
    info['disk_free_gb'] = disk.free / (1024**3)
    info['disk_percent'] = disk.percent
    
    return info

def estimate_pdf_memory_usage():
    """
    Estima memoria por PDF en proceso OCR.
    ocrmypdf puede usar 200-500 MB por PDF según complejidad.
    """
    return 0.5  # GB por proceso (estimación conservadora)

def recommend_workers(info):
    """
    Recomienda número de workers basado en recursos del sistema.
    
    Criterios:
    1. CPU: 1 worker por core físico (deja 1-2 cores libres)
    2. RAM: Suficiente para workers + sistema (mínimo 2GB libres)
    3. I/O: No saturar disco
    """
    recommendations = {}
    
    # Recomendación basada en CPU
    cpu_physical = info['cpu_count_physical'] or info['cpu_count_logical'] // 2
    cpu_recommendation = max(1, cpu_physical - 1)  # Dejar 1 core libre
    
    # Recomendación basada en RAM
    ram_available = info['ram_available_gb']
    memory_per_worker = estimate_pdf_memory_usage()
    system_reserved = 2.0  # Reservar 2GB para el sistema
    ram_recommendation = max(1, int((ram_available - system_reserved) / memory_per_worker))
    
    # Recomendación basada en disco (espacio libre)
    disk_recommendation = float('inf')  # Sin límite si hay espacio
    if info['disk_free_gb'] < 50:
        disk_recommendation = 2  # Conservador si queda poco espacio
    
    # Tomar el mínimo (recurso más limitante)
    recommended = min(cpu_recommendation, ram_recommendation, disk_recommendation)
    recommended = max(1, min(recommended, 16))  # Entre 1 y 16 workers
    
    recommendations['cpu_based'] = cpu_recommendation
    recommendations['ram_based'] = ram_recommendation
    recommendations['recommended'] = recommended
    recommendations['conservative'] = max(1, recommended // 2)
    recommendations['aggressive'] = min(16, recommended * 2)
    
    return recommendations

def print_system_info(info):
    """Imprime información del sistema"""
    print("\n" + "="*70)
    print("  ANÁLISIS DEL SISTEMA")
    print("="*70)
    
    print(f"\n🖥️  CPU:")
    print(f"   Cores físicos:     {info['cpu_count_physical']}")
    print(f"   Threads lógicos:   {info['cpu_count_logical']}")
    if info['cpu_freq']:
        print(f"   Frecuencia:        {info['cpu_freq'].current:.0f} MHz")
    print(f"   Uso actual:        {info['cpu_percent']:.1f}%")
    
    print(f"\n💾  MEMORIA RAM:")
    print(f"   Total:             {info['ram_total_gb']:.2f} GB")
    print(f"   Disponible:        {info['ram_available_gb']:.2f} GB")
    print(f"   Uso:               {info['ram_percent']:.1f}%")
    
    print(f"\n💿  DISCO (C:):")
    print(f"   Total:             {info['disk_total_gb']:.2f} GB")
    print(f"   Libre:             {info['disk_free_gb']:.2f} GB")
    print(f"   Uso:               {info['disk_percent']:.1f}%")
    
    print(f"\n📊  SISTEMA:")
    print(f"   OS:                {platform.system()} {platform.release()}")
    print(f"   Python:            {sys.version.split()[0]}")

def print_recommendations(rec, info):
    """Imprime recomendaciones"""
    print("\n" + "="*70)
    print("  RECOMENDACIONES DE WORKERS")
    print("="*70)
    
    print(f"\n📈  Análisis de recursos:")
    print(f"   Límite por CPU:    {rec['cpu_based']} workers")
    print(f"   Límite por RAM:    {rec['ram_based']} workers")
    
    print(f"\n✅  RECOMENDACIÓN PRINCIPAL: {rec['recommended']} workers")
    print(f"   (Balance óptimo entre CPU, RAM y estabilidad)")
    
    print(f"\n🔧  Opciones alternativas:")
    print(f"   Conservadora:      {rec['conservative']} workers  (más estable, menos rápido)")
    print(f"   Recomendada:       {rec['recommended']} workers  ⭐ USAR ESTA")
    print(f"   Agresiva:          {rec['aggressive']} workers  (más rápido, más riesgo)")
    
    # Estimaciones de rendimiento
    print(f"\n⏱️  Estimación de tiempo (7,883 PDFs de ~2 páginas):")
    pdfs_per_hour_per_worker = 50
    
    for label, workers in [('Conservadora', rec['conservative']), 
                           ('Recomendada', rec['recommended']), 
                           ('Agresiva', rec['aggressive'])]:
        pdfs_per_hour = pdfs_per_hour_per_worker * workers
        hours = 7883 / pdfs_per_hour
        days = hours / 24
        print(f"   {label:15} ({workers:2} workers): {hours:6.1f}h ({days:4.1f} días) - {pdfs_per_hour:3.0f} PDFs/hora")

def print_usage_examples(rec):
    """Imprime ejemplos de uso"""
    print("\n" + "="*70)
    print("  EJEMPLOS DE USO")
    print("="*70)
    
    print(f"\n🚀  INICIO RÁPIDO (Recomendado: {rec['recommended']} workers):")
    print(f"\n   # Terminal 1: Iniciar Redis")
    print(f"   docker run -d -p 6379:6379 --name redis-ocr redis:latest")
    print(f"\n   # Terminal 2: Iniciar workers")
    print(f"   .\.venv\Scripts\Activate.ps1")
    print(f"   python .\\proyecto\\start_workers.py --workers {rec['recommended']} --concurrency 1")
    print(f"\n   # Terminal 3: Encolar PDFs")
    print(f"   .\.venv\Scripts\Activate.ps1")
    print(f"   python .\\proyecto\\enqueue_pdfs.py --limit 100")
    
    print(f"\n📊  MONITOREO:")
    print(f"   python .\\proyecto\\check_status.py")
    print(f"   celery -A tasks inspect active")

def print_warnings(info, rec):
    """Imprime advertencias si hay limitaciones"""
    print("\n" + "="*70)
    print("  ⚠️  ADVERTENCIAS")
    print("="*70)
    
    warnings = []
    
    if info['ram_available_gb'] < 4:
        warnings.append(f"   ⚠️  RAM disponible baja ({info['ram_available_gb']:.1f}GB). Usa máximo {rec['conservative']} workers.")
    
    if info['disk_free_gb'] < 50:
        warnings.append(f"   ⚠️  Espacio en disco bajo ({info['disk_free_gb']:.1f}GB). Monitorea el espacio.")
    
    if info['cpu_percent'] > 70:
        warnings.append(f"   ⚠️  CPU con uso alto ({info['cpu_percent']:.1f}%). Cierra programas innecesarios.")
    
    if info['ram_percent'] > 80:
        warnings.append(f"   ⚠️  RAM con uso alto ({info['ram_percent']:.1f}%). Cierra programas innecesarios.")
    
    if warnings:
        for w in warnings:
            print(w)
    else:
        print("   ✅  No se detectaron limitaciones importantes.")
    
    print()

def main():
    print("\n" + "="*70)
    print("  ANÁLISIS DE SISTEMA PARA PROCESAMIENTO OCR MASIVO")
    print("="*70)
    
    try:
        # Obtener información del sistema
        info = get_system_info()
        
        # Calcular recomendaciones
        rec = recommend_workers(info)
        
        # Mostrar resultados
        print_system_info(info)
        print_recommendations(rec, info)
        print_warnings(info, rec)
        print_usage_examples(rec)
        
        print("\n" + "="*70)
        print("  💡 CONSEJOS ADICIONALES")
        print("="*70)
        print("""
   1. Empieza con menos workers y aumenta gradualmente
   2. Monitorea el uso de CPU/RAM con el Administrador de Tareas
   3. Si los workers se quedan sin memoria, reduce el número
   4. Para PDFs muy grandes, reduce workers o aumenta timeout
   5. Usa --concurrency 1 (una tarea por worker es más estable)
        """)
        
    except Exception as e:
        print(f"\n❌ Error analizando el sistema: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
