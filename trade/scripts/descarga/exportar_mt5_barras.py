#!/usr/bin/env python3
"""Exporta barras 1m de un simbolo desde la terminal MT5 abierta y conectada (solo lectura, sin ordenes).
Uso: python scripts/descarga/exportar_mt5_barras.py USTEC 2016-01-01
Los timestamps de MT5 son hora del SERVIDOR del broker (se guardan tal cual como `time_server`); NO se convierten aqui."""
import datetime as dt
import sys
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

sym, desde = sys.argv[1], dt.datetime.fromisoformat(sys.argv[2])
assert mt5.initialize(), mt5.last_error()
mt5.symbol_select(sym, True)
partes, a, hoy = [], desde, dt.datetime.now() + dt.timedelta(days=2)
while a < hoy:
    b = min(a + dt.timedelta(days=60), hoy)
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, a, b)
    if r is not None and len(r):
        partes.append(pd.DataFrame(r))
    a = b
df = pd.concat(partes).drop_duplicates("time").sort_values("time")
df["time_server"] = pd.to_datetime(df["time"], unit="s")
df = df[["time_server", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
out = Path(__file__).resolve().parents[2] / "data" / "raw" / f"{sym}_ICMarkets_demo_1m.csv"
df.to_csv(out, index=False)
print(out, len(df), df.time_server.min(), df.time_server.max())
