#!/usr/bin/env python3
"""
Organiza el proyecto: reubica lo que se usa y aparta lo obsoleto en `_por_borrar/`
(no borra nada de golpe: revisas esa carpeta y la eliminas tu).

Uso (desde la raiz del proyecto, PowerShell):
    python organizar_proyecto.py              # SIMULACION: solo muestra lo que haria
    python organizar_proyecto.py --aplicar    # ejecuta

Las cachas regenerables (__pycache__, .pytest_cache) si se borran directamente.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PAPELERA = RAIZ / "_por_borrar"

# (origen, destino) relativos a la raiz: se MUEVEN a su lugar definitivo
REUBICAR = [
    ("data/raw/NQ_databento_1m_2016_2021_RTH.csv.zst", "data/raw/databento_crudo/NQ_databento_1m_2016_2021_RTH.csv.zst"),
    ("data/raw/ES_databento_1m_10y_RTH.csv.zst", "data/raw/databento_crudo/ES_databento_1m_10y_RTH.csv.zst"),
    ("data/raw/NQ_rolls.csv", "data/raw/calidad/NQ_rolls.csv"),
    ("data/raw/ES_rolls.csv", "data/raw/calidad/ES_rolls.csv"),
    ("data/raw/reporte_calidad_validacion.txt", "data/raw/calidad/reporte_calidad_validacion.txt"),
    ("scripts/marco_subastas.py", "scripts/marco_subastas/marco_subastas.py"),
    ("scripts/marco_subastas_stop_amplio.py", "scripts/marco_subastas/marco_subastas_stop_amplio.py"),
    ("scripts/marco_contexto_salidas.py", "scripts/marco_subastas/marco_contexto_salidas.py"),
]

# Obsoleto o duplicado: va a _por_borrar/ conservando su ruta relativa
OBSOLETO = [
    # descargadores viejos (reemplazados por scripts/descarga/)
    "descargar_databento.py", "descargar_databento_v2.py",
    "descargar_databento_5anios.py", "descargar_validacion.py",
    # analisis de rondas anteriores (yfinance / 1 anio / 5m) ya superados por scripts/g2 y marco_subastas
    "scripts/grid_databento.py", "scripts/validar_databento.py", "scripts/horarios_sin_gaps.py",
    "scripts/validar_sin_gaps.py", "scripts/trades_ultimos_dias.py", "scripts/analisis_movimiento.py",
    "scripts/descargar_tiingo.py", "scripts/archivo",
    # copias duplicadas de resultados G2 (el definitivo esta en resultados/g2/)
    "scripts/g2/resultado_validacion.log", "scripts/g2/resumen_decision.csv",
    # datos derivados regenerables y archivos ya unidos en NQ_databento_1m_10y_RTH.csv.gz
    "data/raw/NQ_databento_5m.csv", "data/raw/NQ_databento_15m.csv", "data/raw/NQ_databento_30m.csv",
    "data/raw/NQ_databento_1h.csv", "data/raw/NQ_databento_1m_5y_RTH.csv",
    "data/raw/NQ_databento_1m_2016_2021_RTH.csv.gz", "data/raw/_tramos",
    "data/processed/NQ_1h_indicadores.csv", "data/processed/NQ_5m_indicadores.csv",
]
# Resultados: se aparta todo salvo lo que documenta el marco de subastas
RESULTADOS_CONSERVAR = {
    "marco_subastas_resultados.csv", "marco_subastas_stop_amplio.csv", "marco_subastas_mejor_variante_trades.csv",
}
CACHES = ["__pycache__", ".pytest_cache"]

# Archivos imprescindibles: si faltan, no se toca nada
REQUERIDOS = [  # (rutas alternativas, tamano minimo en bytes)
    (["data/raw/NQ_databento_1m_10y_RTH.csv.gz"], 5_000_000),
    (["data/raw/ES_databento_1m_10y_RTH.csv.gz"], 5_000_000),
    (["data/raw/NQ_databento_1m_2016_2021_RTH.csv.zst", "data/raw/databento_crudo/NQ_databento_1m_2016_2021_RTH.csv.zst"], 1_000_000),
    (["data/raw/ES_databento_1m_10y_RTH.csv.zst", "data/raw/databento_crudo/ES_databento_1m_10y_RTH.csv.zst"], 1_000_000),
]


def tam(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def destino_libre(dst: Path) -> Path:
    if not dst.exists():
        return dst
    i = 1
    while True:
        cand = dst.with_name(f"{dst.stem}__{i}{dst.suffix}")
        if not cand.exists():
            return cand
        i += 1


def construir_plan() -> tuple[list, list, list]:
    mover, archivar, limpiar = [], [], []
    for o, d in REUBICAR:
        if (RAIZ / o).exists():
            mover.append((RAIZ / o, RAIZ / d))
    for o in OBSOLETO:
        if (RAIZ / o).exists():
            archivar.append((RAIZ / o, PAPELERA / o))
    for sub in ("csv", "png"):
        carpeta = RAIZ / "resultados" / sub
        if carpeta.is_dir():
            for f in sorted(carpeta.iterdir()):
                if f.is_file() and f.name != ".gitkeep" and f.name not in RESULTADOS_CONSERVAR:
                    archivar.append((f, PAPELERA / "resultados" / sub / f.name))
    for c in CACHES:
        for p in RAIZ.rglob(c):
            if PAPELERA not in p.parents and p.is_dir():
                limpiar.append(p)
    return mover, archivar, limpiar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="ejecuta (por defecto solo simula)")
    a = ap.parse_args()

    faltan = [r[0] for r, minimo in REQUERIDOS if not any((RAIZ / x).exists() and tam(RAIZ / x) >= minimo for x in r)]
    if faltan:
        print("ABORTADO: faltan archivos imprescindibles (o estan incompletos):")
        for r in faltan:
            print("  -", r)
        print("No se ha tocado nada.")
        return 1

    mover, archivar, limpiar = construir_plan()
    modo = "EJECUTANDO" if a.aplicar else "SIMULACION (no se toca nada; usa --aplicar para ejecutar)"
    print(f"== {modo} ==\n")
    print("1) Reubicar (se conservan):")
    for s, d in mover:
        print(f"   {s.relative_to(RAIZ)}  ->  {d.relative_to(RAIZ)}")
    total = 0
    print("\n2) Apartar en _por_borrar/ (obsoleto o duplicado):")
    for s, d in archivar:
        t = tam(s)
        total += t
        print(f"   {s.relative_to(RAIZ)}  ({mb(t)})")
    print(f"\n3) Borrar cachas regenerables: {len(limpiar)} carpetas")
    print(f"\nEspacio que quedara en _por_borrar/: {mb(total)}")

    if not a.aplicar:
        return 0

    log = []
    for s, d in mover:
        d.parent.mkdir(parents=True, exist_ok=True)
        d = destino_libre(d)
        shutil.move(str(s), str(d))
        log.append(f"MOVIDO {s.relative_to(RAIZ)} -> {d.relative_to(RAIZ)}")
    for s, d in archivar:
        d.parent.mkdir(parents=True, exist_ok=True)
        d = destino_libre(d)
        shutil.move(str(s), str(d))
        log.append(f"APARTADO {s.relative_to(RAIZ)} -> {d.relative_to(RAIZ)}")
    for p in limpiar:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            log.append(f"CACHE BORRADA {p.relative_to(RAIZ)}")
    # carpetas necesarias para que los scripts escriban sin fallar
    for d in ("data/processed", "resultados/g2", "resultados/csv", "resultados/png", "resultados/reportes"):
        (RAIZ / d).mkdir(parents=True, exist_ok=True)
    (RAIZ / "organizar_proyecto.log").write_text("\n".join(log), encoding="utf-8")
    print("\nListo. Registro en organizar_proyecto.log")
    print("Cuando revises _por_borrar/ y estes de acuerdo, eliminala con:")
    print("    Remove-Item -Recurse -Force _por_borrar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
