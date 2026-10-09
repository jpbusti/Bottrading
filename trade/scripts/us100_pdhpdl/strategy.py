"""Logica de senales de US100 PDH/PDL. SOLO senales: sin fills ni costos (ver simulador.py).

Reglas (parametros en config.yaml):
  1. PDH/PDL = maximo/minimo de la sesion RTH anterior (columnas pdh/pdl de datos.preparar). `lag` > 0 usa los niveles de hace
     `lag` dias habiles adicionales (SOLO para el placebo de nivel).
  2. Toque = primera barra del dia (09:30 .. ultima_entrada) con high >= PDH (corto) / low <= PDL (largo). Un solo primer toque por nivel.
  3. Reaccion: la barra de toque debe cerrar del lado de rechazo (close < PDH / close > PDL). Si cierra mas alla, ese nivel no se opera.
  4. Entrada en la apertura de la barra siguiente; hasta un trade por nivel y dia.
La senal es independiente de k y m (SL/TP): estos solo se aplican en simulador.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def generar_senales(b: pd.DataFrame, cfg: dict, lag: int = 0, ultima_entrada: str | None = None,
                    rechazo_cierre: bool | None = None) -> pd.DataFrame:
    """b: barras con fecha, open, high, low, close, pdh, pdl; indice = hora ET.

    Devuelve una fila por senal: fecha, d (+1 largo en PDL / -1 corto en PDH), nivel, i_senal, i_entrada, hora_entrada.
    """
    tf = cfg["datos"]["timeframe_min"]
    ue = ultima_entrada or cfg["sesion"]["ultima_entrada"]
    rech = cfg["niveles"]["rechazo_cierre"] if rechazo_cierre is None else rechazo_cierre
    max_idx = (_min(ue) - _min(cfg["sesion"]["inicio"])) // tf
    fechas = b.fecha.values
    ini = np.r_[0, np.flatnonzero(fechas[1:] != fechas[:-1]) + 1]
    fin = np.r_[ini[1:], len(fechas)]
    H, L, C = b.high.values, b.low.values, b.close.values
    pdh_d = np.array([b.pdh.values[a] for a in ini])
    pdl_d = np.array([b.pdl.values[a] for a in ini])
    filas = []
    for k, (a, z) in enumerate(zip(ini, fin)):
        if k - lag < 0:
            continue
        kk = k - lag
        pdh, pdl = pdh_d[kk], pdl_d[kk]          # niveles que habria usado el dia kk (maximo/minimo del dia habil previo a kk)
        if not (np.isfinite(pdh) and np.isfinite(pdl)):
            continue
        jmax = min(z - 2, a + max_idx)          # debe existir barra siguiente para entrar
        if jmax < a:
            continue
        for d, nivel in ((-1, pdh), (1, pdl)):
            if d == -1:
                toca = np.flatnonzero(H[a:jmax + 1] >= nivel)
            else:
                toca = np.flatnonzero(L[a:jmax + 1] <= nivel)
            if len(toca) == 0:
                continue
            j = a + int(toca[0])
            if rech and (C[j] >= nivel if d == -1 else C[j] <= nivel):
                continue                          # cierra mas alla del nivel: ruptura, no rechazo
            filas.append(dict(fecha=fechas[a], d=d, nivel=float(nivel), i_senal=int(j), i_entrada=int(j + 1),
                              hora_entrada=b.index[j + 1]))
    return pd.DataFrame(filas, columns=["fecha", "d", "nivel", "i_senal", "i_entrada", "hora_entrada"])
