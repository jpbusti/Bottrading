"""Rellena los dias de NQ ausentes en NQ_1m_RTH_frontmonth_10y (viernes de vencimiento, NQ.c.0 sin datos) y escribe *_v2.

Descarga NQ.FUT (parent) solo esos dias, elige el contrato de mayor volumen del dia (misma regla que el ZST).
Clave solo por DATABENTO_API_KEY. Coste ~ $0.01 por dia.
"""
from __future__ import annotations

import os
from pathlib import Path

import databento as db
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth_10y.csv.gz"
ES = BASE / "data/raw/es/ES_1m_RTH_frontmonth.csv.gz"
OUT = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth_10y_v2.csv.gz"


def dias(path):
    d = pd.read_csv(path)
    d["Datetime"] = pd.to_datetime(d["Datetime"], utc=True).dt.tz_convert("America/New_York")
    return d


def main():
    assert os.environ.get("DATABENTO_API_KEY"), "falta DATABENTO_API_KEY en el entorno"
    n, e = dias(SRC), dias(ES)
    faltan = sorted(set(e.Datetime.dt.date) - set(n.Datetime.dt.date))
    print(f"Dias faltantes: {len(faltan)}")
    c = db.Historical()
    partes = []
    for d in faltan:
        st = pd.Timestamp(d)
        df = c.timeseries.get_range(dataset="GLBX.MDP3", symbols=["NQ.FUT"], stype_in="parent", schema="ohlcv-1m",
                                    start=st.strftime("%Y-%m-%d"), end=(st + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                                    ).to_df().reset_index()
        df = df[~df["symbol"].str.contains("-", na=False)]
        df["Datetime"] = pd.to_datetime(df["ts_event"], utc=True).dt.tz_convert("America/New_York")
        t = df["Datetime"].dt.time
        df = df[(t >= pd.Timestamp("09:30").time()) & (t <= pd.Timestamp("15:59").time()) & (df["Datetime"].dt.date == d)]
        fm = df.groupby("symbol")["volume"].sum().idxmax()
        df = df[df["symbol"] == fm]
        print(f"  {d}: {fm} {len(df)} barras")
        partes.append(df[["Datetime", "open", "high", "low", "close", "volume", "symbol"]].set_axis(
            ["Datetime", "Open", "High", "Low", "Close", "Volume", "Symbol"], axis=1))
    full = pd.concat([n] + partes).sort_values("Datetime").drop_duplicates("Datetime")
    full.to_csv(OUT, index=False, compression="gzip")
    print(f"v2: {len(full):,} filas, {full['Datetime'].dt.date.nunique()} dias -> {OUT}")


if __name__ == "__main__":
    main()
