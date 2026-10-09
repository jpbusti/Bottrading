"""Logica de senales de US100 ORB filtrado. SOLO senales: sin simulacion de fills ni costos (ver simulador.py).

Reglas (parametros en config.yaml, nada hardcodeado):
  1. Opening Range = maximo/minimo de las primeras `opening_range.minutos` de la sesion.
  2. Ruptura = primera barra tras el OR cuyo CIERRE queda fuera del OR (por encima del maximo: largo; por debajo: corto).
  3. Filtros evaluados al cierre de la barra de ruptura (solo informacion pasada):
       - VWAP de sesion con pendiente a favor (VWAP[t] - VWAP[t-n]).
       - Volumen de la barra > multiplo x media de las `ventana` barras previas.
  4. Retest: dentro de `max_barras` barras, una barra toca el nivel roto y CIERRA del lado de la ruptura. Si antes una barra
     cierra de vuelta dentro del OR, la senal se invalida.
  5. Entrada en la APERTURA de la barra siguiente a la confirmacion; a lo sumo un trade por dia.
La senal es independiente de k y m (SL/TP); estos solo se aplican en simulador.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def agregar_indicadores(b: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Anade `vwap` (anclado a la sesion, precio tipico) y `vol_rel` (volumen / media de las `ventana` barras previas)."""
    b = b.copy()
    tp = (b.high + b.low + b.close) / 3
    pv = (tp * b.volume).groupby(b.fecha).cumsum()
    v = b.volume.groupby(b.fecha).cumsum()
    b["vwap"] = pv / v.where(v > 0)
    w = cfg["filtros"]["volumen"]["ventana"]
    b["vol_rel"] = b.volume / b.volume.shift(1).rolling(w).mean()
    return b


def _hhmm_a_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def generar_senales(b: pd.DataFrame, cfg: dict, lag_or: int = 0) -> pd.DataFrame:
    """b: barras con columnas fecha, open, high, low, close, vwap, vol_rel (ver agregar_indicadores), indice = hora ET.

    lag_or: dia del que sale el OR (0 = el propio dia; N>0 = OR de hace N dias habiles, SOLO para el placebo de nivel).
    Devuelve una fila por senal: fecha, d (+1/-1), nivel, i_confirma, i_entrada (posiciones en `b`), hora_entrada.
    """
    tf = cfg["datos"]["timeframe_min"]
    n_or = cfg["opening_range"]["minutos"] // tf
    f = cfg["filtros"]
    max_idx = (_hhmm_a_min(cfg["sesion"]["ultima_entrada"]) - _hhmm_a_min(cfg["sesion"]["inicio"])) // tf
    fechas = b.fecha.values
    ini = np.r_[0, np.flatnonzero(fechas[1:] != fechas[:-1]) + 1]
    fin = np.r_[ini[1:], len(fechas)]
    H, L, C = b.high.values, b.low.values, b.close.values
    VW, VR = b.vwap.values, b.vol_rel.values
    filas = []
    for k, (a, z) in enumerate(zip(ini, fin)):
        if k - lag_or < 0 or z - a <= n_or + 1:
            continue
        a0 = ini[k - lag_or]
        if fin[k - lag_or] - a0 < n_or:
            continue
        orh, orl = H[a0:a0 + n_or].max(), L[a0:a0 + n_or].min()
        jmax = min(z - 1, a + max_idx)
        j = next((q for q in range(a + n_or, jmax) if C[q] > orh or C[q] < orl), None)
        if j is None:
            continue
        d = 1 if C[j] > orh else -1
        nivel = orh if d == 1 else orl
        if f["vwap_pendiente"]["activo"]:
            n = f["vwap_pendiente"]["barras"]
            if j - n < a or not np.isfinite(VW[j]) or not np.isfinite(VW[j - n]) or d * (VW[j] - VW[j - n]) <= 0:
                continue
        if f["volumen"]["activo"] and not (VR[j] > f["volumen"]["multiplo"]):
            continue
        if f["retest"]["activo"]:
            tol = f["retest"]["tolerancia_pts"]
            conf = None
            for q in range(j + 1, min(j + f["retest"]["max_barras"], jmax - 1) + 1):
                if d * (C[q] - nivel) <= 0:                         # cierra de vuelta dentro del OR: invalida
                    break
                if (L[q] <= nivel + tol) if d == 1 else (H[q] >= nivel - tol):
                    conf = q
                    break
            if conf is None:
                continue
        else:
            conf = j
        if conf + 1 >= z or conf + 1 - a > max_idx:
            continue
        filas.append(dict(fecha=fechas[a], d=d, nivel=float(nivel), i_confirma=int(conf), i_entrada=int(conf + 1),
                          hora_entrada=b.index[conf + 1]))
    return pd.DataFrame(filas, columns=["fecha", "d", "nivel", "i_confirma", "i_entrada", "hora_entrada"])
