"""
ANÁLISIS DE TRAYECTORIA POST-TOQUE de PDH/PDL (MFE/MAE, curvas TP/SL sin SL/TP previos).

Las funciones viven en scripts/pdh_pdl_lab.py (se movió el laboratorio entero sin tocar su
lógica); este módulo es el punto de entrada propio del análisis.

Uso (desde la raíz del proyecto):  python -m scripts.analisis_movimiento
"""
from scripts.pdh_pdl_lab import (analizar_movimiento_post_toque, analisis_movimiento_real,
                                 main_movimiento)

__all__ = ["analizar_movimiento_post_toque", "analisis_movimiento_real", "main_movimiento"]

if __name__ == "__main__":
    main_movimiento()
