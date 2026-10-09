"""Simulacion de fills, SL/TP y costos para us100_orb. Recibe las senales de strategy.py; no decide entradas."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from validacion.cost_model import costo_trade_cfd  # noqa: E402


def _min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def costo_pts(cfg: dict, spread: float | None = None) -> float:
    """Costo ida y vuelta en puntos (spread + 2 x slippage por lado + comision 0) via validacion/cost_model.py."""
    c = cfg["costos"]
    return costo_trade_cfd(cfg["instrumento"]["clave_costos"], spread_pts=c["spread_pts"]["base"] if spread is None else spread,
                           slippage_pts_lado=c["slippage_pts_lado"])["total_pts"]


def idx_salida(b: pd.DataFrame, cfg: dict) -> pd.Series:
    """Posicion de la barra de salida forzada de cada dia, indexada por fecha."""
    hh = b.index.hour * 60 + b.index.minute
    marca = np.asarray(hh == _min(cfg["sesion"]["salida_forzada"]))
    pos = np.arange(len(b))[marca]
    return pd.Series(pos, index=b.fecha.values[marca]).groupby(level=0).last()


def simular(H, L, C, O, i_ent: int, i_sal: int, d: int, sl: float, tp: float, costo: float):
    """Entrada en la apertura de la barra i_ent. SL antes que TP si ambos tocan en la misma barra. (R neta, pnl_pts, motivo)."""
    entry = O[i_ent]
    hh, ll = H[i_ent:i_sal + 1], L[i_ent:i_sal + 1]
    ps = ll <= entry - sl if d == 1 else hh >= entry + sl
    pt = hh >= entry + tp if d == 1 else ll <= entry - tp
    i_sl = int(np.argmax(ps)) if ps.any() else 10 ** 9
    i_tp = int(np.argmax(pt)) if pt.any() else 10 ** 9
    if i_sl <= i_tp and i_sl < 10 ** 9:
        pnl, mot = -sl, "SL"
    elif i_tp < 10 ** 9:
        pnl, mot = tp, "TP"
    else:
        pnl, mot = d * (C[i_sal] - entry), "T"
    return (pnl - costo) / sl, pnl, mot


def simular_trades(b: pd.DataFrame, senales: pd.DataFrame, cfg: dict, invertir: bool = False, costo: float | None = None,
                   timing_rng: np.random.Generator | None = None, combos=None) -> pd.DataFrame:
    """Una fila por (senal, combo). combo=(k, m): SL=k*ATR_d, TP=m*ATR_d. Columnas: fecha, anio, combo, d, R, pnl, motivo, entry.

    invertir: placebo de direccion (re-simula con d invertida). timing_rng: placebo de timing (barra de entrada y direccion al
    azar entre la primera barra tras el OR y la ultima de entrada; mismos dias)."""
    costo = costo_pts(cfg) if costo is None else costo
    combos = combos or [(k, m) for k in cfg["riesgo"]["k_sl"] for m in cfg["riesgo"]["m_tp"]]
    salidas = idx_salida(b, cfg)
    H, L, C, O = b.high.values, b.low.values, b.close.values, b.open.values
    atr = b.atr_d.values
    ini = pd.Series(np.arange(len(b)), index=b.fecha.values).groupby(level=0).first()
    tf = cfg["datos"]["timeframe_min"]
    n_or = cfg["opening_range"]["minutos"] // tf
    max_idx = (_min(cfg["sesion"]["ultima_entrada"]) - _min(cfg["sesion"]["inicio"])) // tf
    filas = []
    for s in senales.itertuples():
        if s.fecha not in salidas.index:
            continue
        i_ent, d = s.i_entrada, s.d
        if timing_rng is not None:
            i_ent = int(ini[s.fecha] + timing_rng.integers(n_or, max_idx + 1))
            d = 1 if timing_rng.random() < 0.5 else -1
        elif invertir:
            d = -d
        i_sal = int(salidas[s.fecha])
        if i_ent > i_sal or not np.isfinite(atr[i_ent]):
            continue
        for k, m in combos:
            sl, tp = k * atr[i_ent], m * atr[i_ent]
            if sl <= 0:
                continue
            r, pnl, mot = simular(H, L, C, O, i_ent, i_sal, d, sl, tp, costo)
            filas.append(dict(fecha=s.fecha, anio=pd.Timestamp(s.fecha).year, combo=(k, m), d=d, R=r, pnl=pnl, motivo=mot,
                              entry=O[i_ent]))
    return pd.DataFrame(filas, columns=["fecha", "anio", "combo", "d", "R", "pnl", "motivo", "entry"])
