"""Limpiar USTEC_ICMarkets_demo_1m.csv:

1. Separar tramo diario (time=00:00) -> archivar en data/_archivo/
2. Descartar tramo 1m anterior a 2018-01-01 (resolucion horaria disfrazada)
3. Dividir spread / 100 para obtener puntos (spread=200 -> 2.0 pts)
4. Convertir timestamps server time (ET+7) a ET (restar 7 horas, offset fijo)
5. Guardar como data/raw/us100/USTEC_1m_clean_2018_2026.csv

Uso: python scripts/descarga/limpiar_ustec.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "data/raw/us100/USTEC_ICMarkets_demo_1m.csv"
OUT = BASE / "data/raw/us100/USTEC_1m_clean_2018_2026.csv"
ARCHIVO_DIARIO = BASE / "data/_archivo/USTEC_daily_2012_2025.csv"
CORTE_FECHA = pd.Timestamp("2018-01-01")
OFFSET_HORAS = 7   # server = ET + 7h (fijo; ambas regiones cambian DST juntas)


def main():
    print(f"Leyendo {SRC} ...")
    df = pd.read_csv(SRC, parse_dates=["time_server"])
    print(f"  Filas totales: {len(df):,}")

    # --- Separar diario (time=00:00) ---
    is_daily = df["time_server"].dt.time == pd.Timestamp("00:00:00").time()
    daily = df[is_daily].copy()
    intra = df[~is_daily].copy()
    print(f"  Diario: {len(daily):,} filas ({daily['time_server'].min().date()} -> {daily['time_server'].max().date()})")
    print(f"  1m:     {len(intra):,} filas ({intra['time_server'].min()} -> {intra['time_server'].max()})")

    # Archivar tramo diario
    ARCHIVO_DIARIO.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(ARCHIVO_DIARIO, index=False)
    print(f"  Tramo diario archivado en: {ARCHIVO_DIARIO}")

    # --- Filtrar >= 2018-01-01 ---
    intra = intra[intra["time_server"] >= CORTE_FECHA].copy()
    print(f"  Filas >= 2018-01-01: {len(intra):,}")

    # --- Convertir timestamp a ET ---
    # server_time = ET + 7h -> ET = server_time - 7h
    intra["time_et"] = intra["time_server"] - pd.Timedelta(hours=OFFSET_HORAS)

    # --- Convertir spread a puntos ---
    intra["spread_pts"] = intra["spread"] / 100.0

    # --- Seleccionar y renombrar columnas ---
    out = intra[["time_et", "open", "high", "low", "close", "tick_volume", "spread_pts", "real_volume"]].copy()
    out = out.rename(columns={"time_et": "Datetime", "open": "Open", "high": "High", "low": "Low",
                               "close": "Close", "tick_volume": "TickVolume",
                               "spread_pts": "Spread_pts", "real_volume": "RealVolume"})
    out = out.sort_values("Datetime").reset_index(drop=True)

    # --- Estadisticas ---
    print(f"\n--- Estadisticas del archivo limpio ---")
    print(f"  Filas: {len(out):,}")
    print(f"  Rango ET: {out['Datetime'].min()} -> {out['Datetime'].max()}")
    print(f"  Spread_pts medio: {out['Spread_pts'].mean():.3f}")
    print(f"  Spread_pts mediana: {out['Spread_pts'].median():.3f}")
    print(f"  TickVolume > 0: {(out['TickVolume'] > 0).mean() * 100:.1f}%")
    print(f"  RealVolume == 0: {(out['RealVolume'] == 0).mean() * 100:.1f}%")

    # Verificar que no hay datos 2016-2017
    anios = sorted(out["Datetime"].dt.year.unique())
    print(f"  Anios cubiertos: {anios}")
    assert min(anios) >= 2018, "ERROR: hay datos anteriores a 2018"

    # Verificar spread en rango razonable (0.5 - 5.0 pts para US100)
    spread_ok = out[(out["Spread_pts"] >= 0.5) & (out["Spread_pts"] <= 5.0)]["Spread_pts"]
    print(f"  Spread en rango 0.5-5.0 pts: {len(spread_ok) / len(out) * 100:.1f}%")

    # --- Guardar ---
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    size_mb = OUT.stat().st_size / 1e6
    print(f"\nGuardado: {OUT}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
