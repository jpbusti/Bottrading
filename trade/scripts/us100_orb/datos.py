"""Carga de barras y preparacion de columnas para us100_orb. Sin logica de senales (ver strategy.py)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]


def _a_et_naive(idx: pd.Series, cfg: dict) -> pd.DatetimeIndex:
    """Hora de pared de Nueva York sin zona."""
    if cfg["datos"]["fuente"] == "us100":
        return pd.DatetimeIndex(idx - pd.Timedelta(hours=cfg["datos"]["offset_servidor_h"]))
    return pd.DatetimeIndex(pd.to_datetime(idx, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None))


def cargar_1m(cfg: dict) -> pd.DataFrame:
    """Barras de 1m -> DataFrame(open, high, low, close, volume) indexado por hora ET de pared."""
    ruta = RAIZ / cfg["datos"]["archivos"][cfg["datos"]["fuente"]]
    if cfg["datos"]["fuente"] == "us100":
        d = pd.read_csv(ruta, parse_dates=["time_server"])
        d = d.rename(columns={"tick_volume": "volume"})
        et = _a_et_naive(d["time_server"], cfg)
    else:
        d = pd.read_csv(ruta, index_col=0).rename(columns=str.lower)
        et = _a_et_naive(pd.Series(d.index), cfg)
    d = d[["open", "high", "low", "close", "volume"]].astype(float)
    d.index = et
    d = d[d.index >= cfg["datos"]["desde"]]
    return d[~d.index.duplicated()].sort_index()


def a_barras(d1: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Resample a timeframe_min dentro de la sesion RTH. Descarta barras fuera de [inicio, fin)."""
    tf = f"{cfg['datos']['timeframe_min']}min"
    r = d1.resample(tf).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
    hhmm = r.index.hour * 60 + r.index.minute
    ini = pd.Timestamp(f"2000-01-01 {cfg['sesion']['inicio']}")
    fin = pd.Timestamp(f"2000-01-01 {cfg['sesion']['fin']}")
    r = r[(hhmm >= ini.hour * 60 + ini.minute) & (hhmm < fin.hour * 60 + fin.minute)]
    r["fecha"] = r.index.date
    return r


def atr_diario(b: pd.DataFrame, periodo: int) -> pd.Series:
    """ATR(periodo) diario RTH usando SOLO dias anteriores (D-1 y antes): sin look-ahead. Indexado por fecha."""
    g = b.groupby("fecha").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift(1)
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(periodo).mean().shift(1)


def preparar(cfg: dict) -> pd.DataFrame:
    """Pipeline completo: 1m -> barras RTH -> columna atr_d (ATR diario previo). Solo dias con >= 70% de las barras."""
    b = a_barras(cargar_1m(cfg), cfg)
    n_esp = int(round((_min(cfg["sesion"]["fin"]) - _min(cfg["sesion"]["inicio"])) / cfg["datos"]["timeframe_min"]))
    cuenta = b.groupby("fecha").size()
    b = b[b.fecha.map(cuenta) >= 0.7 * n_esp]
    b["atr_d"] = b.fecha.map(atr_diario(b, cfg["atr"]["periodo"]))
    return b


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
