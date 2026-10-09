"""Carga de barras y preparacion para us100_pdhpdl: barras 5m RTH con ATR diario previo y PDH/PDL del dia anterior."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def cargar_1m(cfg: dict) -> pd.DataFrame:
    """Barras 1m -> DataFrame(open, high, low, close, volume, spread) indexado por hora ET de pared."""
    fuente = cfg["datos"]["fuente"]
    ruta = RAIZ / cfg["datos"]["archivos"][fuente]
    if fuente == "us100":
        d = pd.read_csv(ruta, parse_dates=["Datetime"]).rename(columns={"TickVolume": "volume", "Spread_pts": "spread"})
        d = d.rename(columns=str.lower).set_index("datetime")
        et = pd.DatetimeIndex(d.index)
    else:
        d = pd.read_csv(ruta, index_col=0).rename(columns=str.lower)
        d["spread"] = np.nan
        et = pd.DatetimeIndex(pd.to_datetime(d.index, utc=True).tz_convert("America/New_York").tz_localize(None))
    d = d[["open", "high", "low", "close", "volume", "spread"]].astype(float)
    d.index = et
    d = d[d.index >= cfg["datos"]["desde"][fuente]]
    return d[~d.index.duplicated()].sort_index()


def a_barras(d1: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Resample a timeframe_min dentro de la sesion RTH [inicio, fin). Agrega `spread` (media) para costos por anio."""
    tf = f"{cfg['datos']['timeframe_min']}min"
    r = d1.resample(tf).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
                             "spread": "mean"}).dropna(subset=["open"])
    hhmm = r.index.hour * 60 + r.index.minute
    r = r[(hhmm >= _min(cfg["sesion"]["inicio"])) & (hhmm < _min(cfg["sesion"]["fin"]))].copy()
    r["fecha"] = r.index.date
    return r


def atr_diario(b: pd.DataFrame, periodo: int) -> pd.Series:
    """ATR(periodo) diario RTH con SOLO dias anteriores (D-1 y antes). Indexado por fecha."""
    g = b.groupby("fecha").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pc = g.c.shift(1)
    tr = pd.concat([g.h - g.l, (g.h - pc).abs(), (g.l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(periodo).mean().shift(1)


def preparar(cfg: dict) -> pd.DataFrame:
    """1m -> barras 5m RTH (dias con >= 70% de las barras) con columnas atr_d, pdh, pdl (maximo/minimo RTH del dia habil anterior)."""
    b = a_barras(cargar_1m(cfg), cfg)
    n_esp = int(round((_min(cfg["sesion"]["fin"]) - _min(cfg["sesion"]["inicio"])) / cfg["datos"]["timeframe_min"]))
    cuenta = b.groupby("fecha").size()
    b = b[b.fecha.map(cuenta) >= 0.7 * n_esp].copy()
    b["atr_d"] = b.fecha.map(atr_diario(b, cfg["atr"]["periodo"]))
    g = b.groupby("fecha").agg(h=("high", "max"), l=("low", "min"))
    b["pdh"] = b.fecha.map(g.h.shift(1))
    b["pdl"] = b.fecha.map(g.l.shift(1))
    return b


def spread_por_anio(b: pd.DataFrame) -> pd.Series:
    """Spread mediano observado (puntos) por anio durante RTH. Vacio si la fuente no trae spread (NQ)."""
    s = b.spread.dropna()
    return s.groupby(pd.DatetimeIndex(s.index).year).median() if len(s) else pd.Series(dtype=float)
