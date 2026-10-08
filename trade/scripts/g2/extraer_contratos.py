#!/usr/bin/env python3
"""
Extrae de los .csv.zst crudos de Databento las velas RTH (09:30-16:00 NY) de los
2 contratos outright mas liquidos de cada dia (no spreads), SIN armar serie continua.
Salida: <RAIZ>_contratos_rth.pkl (DataFrame: Datetime, symbol, Open..Volume, fecha).

Uso (desde la raiz del proyecto): python scripts/g2/extraer_contratos.py
(opcional: <carpeta_raw> <carpeta_salida>; por defecto data/raw/databento_crudo -> data/processed)
"""
import io
import logging
import re
import sys
from pathlib import Path

import pandas as pd
import zstandard

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("extraer")
ZONA = "America/New_York"
RAIZ = Path(__file__).resolve().parents[2]
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "raw" / "databento_crudo"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
JOBS = [("NQ_databento_1m_2016_2021_RTH.csv.zst", "NQ"), ("ES_databento_1m_10y_RTH.csv.zst", "ES")]


def procesar(ruta: Path, raiz: str) -> pd.DataFrame:
    patron = re.compile(rf"^{raiz}[FGHJKMNQUVXZ]\d$")
    partes = []
    with open(ruta, "rb") as fh:
        flujo = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh), encoding="utf-8")
        for b in pd.read_csv(flujo, chunksize=500_000,
                             usecols=["ts_event", "open", "high", "low", "close", "volume", "symbol"],
                             dtype={"symbol": "string"}):
            b = b[b["symbol"].str.match(patron, na=False)]
            ts = pd.to_datetime(b["ts_event"], utc=True).dt.tz_convert(ZONA)
            m = ts.dt.hour * 60 + ts.dt.minute
            sel = (m >= 570) & (m < 960)
            b = b.loc[sel].copy()
            b["Datetime"] = ts[sel]
            partes.append(b.drop(columns="ts_event"))
    df = pd.concat(partes, ignore_index=True)
    df["fecha"] = df["Datetime"].dt.date
    vol = df.groupby(["fecha", "symbol"], observed=True)["volume"].sum()
    rk = vol.groupby(level=0).rank(ascending=False, method="first")
    top = set(rk[rk <= 2].index)
    llaves = list(zip(df["fecha"], df["symbol"]))
    df = df[[k in top for k in llaves]].copy()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    df["symbol"] = df["symbol"].astype(str)
    df = df.drop_duplicates(["Datetime", "symbol"]).sort_values(["Datetime", "symbol"]).reset_index(drop=True)
    return df


for zst, raiz in JOBS:
    d = procesar(RAW / zst, raiz)
    p = OUT / f"{raiz}_contratos_rth.pkl"
    d.to_pickle(p)
    log.info("%s: %s velas, %s dias, %s simbolos -> %s", raiz, f"{len(d):,}", d["fecha"].nunique(),
             d["symbol"].nunique(), p)
