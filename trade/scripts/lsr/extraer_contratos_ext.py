#!/usr/bin/env python3
"""Extrae velas 1m 04:00-16:00 ET (premercado + RTH) de los 2 outright mas liquidos por dia (ranking por volumen RTH).
Uso: python extraer_contratos_ext.py <zst_dir> <salida_dir>"""
import io, logging, re, sys
from pathlib import Path
import pandas as pd, zstandard
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("ext")
RAW, OUT = Path(sys.argv[1]), Path(sys.argv[2])
JOBS = [("NQ_databento_1m_2016_2021_RTH.csv.zst", "NQ"), ("ES_databento_1m_10y_RTH.csv.zst", "ES")]

def procesar(ruta, raiz):
    pat = re.compile(rf"^{raiz}[FGHJKMNQUVXZ]\d$")
    partes = []
    with open(ruta, "rb") as fh:
        fl = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh), encoding="utf-8")
        for b in pd.read_csv(fl, chunksize=500_000, usecols=["ts_event","open","high","low","close","volume","symbol"], dtype={"symbol":"string"}):
            b = b[b["symbol"].str.match(pat, na=False)]
            ts = pd.to_datetime(b["ts_event"], utc=True).dt.tz_convert("America/New_York")
            m = ts.dt.hour*60 + ts.dt.minute
            sel = (m >= 240) & (m < 960)
            b = b.loc[sel].copy(); b["Datetime"] = ts[sel]
            partes.append(b.drop(columns="ts_event"))
    df = pd.concat(partes, ignore_index=True)
    df["fecha"] = df["Datetime"].dt.date
    mm = df["Datetime"].dt.hour*60 + df["Datetime"].dt.minute
    vol = df[(mm>=570)].groupby(["fecha","symbol"], observed=True)["volume"].sum()
    rk = vol.groupby(level=0).rank(ascending=False, method="first")
    top = set(rk[rk<=2].index)
    df = df[[k in top for k in zip(df["fecha"], df["symbol"])]].copy()
    df = df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})
    df["symbol"] = df["symbol"].astype(str)
    return df.drop_duplicates(["Datetime","symbol"]).sort_values(["Datetime","symbol"]).reset_index(drop=True)

for z, r in JOBS:
    d = procesar(RAW/z, r); p = OUT/f"{r}_contratos_ext.pkl"; d.to_pickle(p)
    log.info("%s: %s velas, %s dias -> %s", r, f"{len(d):,}", d.fecha.nunique(), p)
