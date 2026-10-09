"""Reconstruir serie ES 1m RTH front-month desde el archivo ZST crudo (Databento multi-contrato).

El ZST ES cubre 2016-2026 completo (verificado en auditoria de datos 2026-10-09).

Uso: python scripts/descarga/reconstruir_frontmonth_es.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import zstandard as zstd

BASE = Path(__file__).resolve().parents[2]
ZST = BASE / "data/raw/databento_crudo/ES_databento_1m_10y_RTH.csv.zst"
OUT = BASE / "data/raw/es/ES_1m_RTH_frontmonth.csv.gz"

RTH_START_UTC_H = 13
RTH_END_UTC_H = 21


def main():
    print(f"Leyendo {ZST} ...")
    with open(ZST, "rb") as f:
        dctx = zstd.ZstdDecompressor()
        reader = dctx.stream_reader(f)
        raw = io.TextIOWrapper(reader, encoding="utf-8")
        df = pd.read_csv(raw)

    print(f"  Filas crudas: {len(df):,}")
    print(f"  Columnas: {list(df.columns)}")
    print(f"  Contratos muestra: {sorted(df['symbol'].unique())[:8]} ...")

    # Filtrar filas de spread (symbol con '-' indica diferencial de roll, precio negativo)
    df = df[~df["symbol"].str.contains("-", na=False)].copy()
    print(f"  Filas tras excluir spreads de roll: {len(df):,}")

    df["ts"] = pd.to_datetime(df["ts_event"], utc=True)
    h = df["ts"].dt.hour
    df = df[(h >= RTH_START_UTC_H) & (h < RTH_END_UTC_H)].copy()
    print(f"  Filas tras filtro RTH: {len(df):,}")

    df["fecha"] = df["ts"].dt.date

    vol_dia = df.groupby(["fecha", "symbol"])["volume"].sum()
    fm = vol_dia.groupby(level="fecha").idxmax().apply(lambda x: x[1])
    print(f"  Dias de trading: {len(fm)}")

    symbols_por_dia = fm.values
    rolls = [(fm.index[i], symbols_por_dia[i - 1], symbols_por_dia[i])
             for i in range(1, len(symbols_por_dia)) if symbols_por_dia[i] != symbols_por_dia[i - 1]]
    print(f"  Rolls detectados: {len(rolls)}")
    for fecha, antes, despues in rolls:
        print(f"    {fecha}: {antes} -> {despues}")

    df["fm"] = df["fecha"].map(fm)
    df_fm = df[df["symbol"] == df["fm"]].copy()
    df_fm = df_fm.sort_values("ts").reset_index(drop=True)
    print(f"  Filas front-month: {len(df_fm):,}")

    # Verificar saltos de precio en rolls
    max_salto = 0.0
    for fecha, _, _ in rolls:
        from datetime import timedelta
        dia_ant = fecha - timedelta(days=1)
        ayer = df_fm[df_fm["fecha"] == dia_ant]
        hoy = df_fm[df_fm["fecha"] == fecha]
        if len(ayer) and len(hoy):
            salto = abs(hoy.iloc[0]["open"] - ayer.iloc[-1]["close"])
            max_salto = max(max_salto, salto)
    print(f"  Salto maximo de precio en rolls: {max_salto:.2f} pts")

    out = df_fm[["ts", "open", "high", "low", "close", "volume", "symbol"]].copy()
    out.columns = ["Datetime", "Open", "High", "Low", "Close", "Volume", "Symbol"]
    out["Datetime"] = out["Datetime"].dt.tz_convert("America/New_York")
    t = out["Datetime"].dt.time
    out = out[(t >= pd.Timestamp("09:30").time()) & (t <= pd.Timestamp("15:59").time())].copy()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, compression="gzip")
    print(f"\nGuardado: {OUT}")
    print(f"  Filas: {len(out):,} | Dias: {out['Datetime'].dt.date.nunique()} | "
          f"Rango: {out['Datetime'].min()} -> {out['Datetime'].max()}")


if __name__ == "__main__":
    main()
