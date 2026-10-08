"""Robustez: rejilla k x m (9 puntos, SL=k*ATR, TP=m*ATR) y sensibilidad "excluir cada anio".

El motor ya genera un registro por (trade, combo) con columna `combo`=(k,m) y `anio`.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from .pf_inference import bootstrap_iid, pf

KS, MS = (0.8, 1.0, 1.2), (1.5, 1.75, 2.0)


def rejilla(df: pd.DataFrame, r_fn: Callable[[pd.DataFrame], np.ndarray], ks=KS, ms=MS, pf_min: float = 1.15) -> dict:
    """PF neto e IC90 en los 9 puntos. Un PF > pf_min en un solo punto es curve-fitting, no robustez."""
    filas = []
    for k in ks:
        for m in ms:
            s = df[df.combo == (k, m)]
            if len(s) == 0:
                continue
            r = r_fn(s)
            b = bootstrap_iid(r)
            filas.append(dict(k=k, m=m, n=len(s), PF=pf(r), pf_lo=b["pf_lo"], expR=float(r.mean())))
    t = pd.DataFrame(filas)
    n_ok = int((t.PF >= pf_min).sum()) if len(t) else 0
    n_lo = int((t.pf_lo > 1.0).sum()) if len(t) else 0
    return dict(tabla=t, n_pf_ok=n_ok, n_lo_gt1=n_lo, n_puntos=len(t),
                robusta=bool(len(t) == len(ks) * len(ms) and n_ok == len(t) and n_lo == len(t)))


def excluir_cada_anio(df: pd.DataFrame, r_fn: Callable[[pd.DataFrame], np.ndarray], umbral_dpf: float = 0.05) -> pd.DataFrame:
    """PF sin cada anio y variacion vs el PF total. `sostiene`=True si ese anio carga el resultado."""
    base = pf(r_fn(df))
    filas = []
    for y in sorted(df.anio.unique()):
        s = df[df.anio != y]
        v = pf(r_fn(s))
        filas.append(dict(sin_anio=y, n=len(s), PF=v, dPF=v - base, sostiene=bool(base - v > umbral_dpf)))
    return pd.DataFrame(filas).set_index("sin_anio")
