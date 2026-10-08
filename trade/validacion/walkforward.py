"""Walk-forward expansivo por anio: entrena con anios < Y, elige la combinacion, prueba en Y.

Movido desde scripts/lsr/motor_lsr.py (mismo comportamiento). El motor aporta `r_fn` (trades -> R neta).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from .pf_inference import pf


def walk_forward(df: pd.DataFrame, r_fn: Callable[[pd.DataFrame], np.ndarray], combo_ref=None,
                 combo_defecto=(1.0, 1.75), anio_ini: int = 2019, min_tr: int = 30):
    """df: una fila por (trade, combo) con columnas `combo` y `anio`.

    Entrena con anios < Y (expansivo), elige el combo (tupla) con mayor PF neto (>= min_tr trades), prueba en Y.
    `combo_ref` se excluye de la eleccion (combo de referencia, no pertenece a la rejilla).
    Devuelve (oos_trades, folds).
    """
    cb_grid = [c for c in sorted(df.combo.unique(), key=str) if isinstance(c, tuple) and c != combo_ref]
    oos, folds = [], []
    for Y in range(anio_ini, int(df.anio.max()) + 1):
        tr, te = df[df.anio < Y], df[df.anio == Y]
        best, bpf = combo_defecto, -1
        for c in cb_grid:
            s = tr[tr.combo == c]
            if len(s) >= min_tr:
                v = pf(r_fn(s))
                if v > bpf:
                    best, bpf = c, v
        t = te[te.combo == best]
        oos.append(t.assign(fold=Y, elegido=str(best)))
        folds.append(dict(fold=Y, combo=best, PF_train=bpf, n_test=len(t),
                          PF_test=pf(r_fn(t)) if len(t) else np.nan,
                          expR=float(r_fn(t).mean()) if len(t) else np.nan))
    return pd.concat(oos, ignore_index=True), pd.DataFrame(folds)


def fragilidad(oos: pd.DataFrame, r_fn: Callable[[pd.DataFrame], np.ndarray], umbral_dpf: float = 0.05) -> pd.DataFrame:
    """PF OOS agrupado sin cada anio. `fragil`=True si quitar ese anio cambia el PF mas de `umbral_dpf`."""
    base = pf(r_fn(oos)) if len(oos) else np.nan
    filas = []
    for y in sorted(oos.anio.unique()):
        s = oos[oos.anio != y]
        v = pf(r_fn(s))
        filas.append(dict(sin_anio=y, n=len(s), PF=v, dPF=v - base, fragil=bool(abs(v - base) > umbral_dpf)))
    return pd.DataFrame(filas).set_index("sin_anio")


def pf_por_fold(oos: pd.DataFrame, r_fn: Callable[[pd.DataFrame], np.ndarray]) -> pd.DataFrame:
    """PF out-of-sample por fold/anio y si TODOS los folds superan 1.0 (criterio de aprobacion)."""
    filas = [dict(anio=y, n=len(g), PF=pf(r_fn(g)), expR=float(r_fn(g).mean())) for y, g in oos.groupby("anio")]
    d = pd.DataFrame(filas).set_index("anio")
    d.attrs["todos_gt1"] = bool((d.PF > 1.0).all()) if len(d) else False
    return d
