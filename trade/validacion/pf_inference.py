"""Metricas e inferencia sobre una serie de resultados en multiplos de riesgo (R, ya netos de costos).

Funciones movidas SIN cambios numericos desde scripts/lsr/motor_lsr.py y scripts/g2/motor_g2.py
(mismos generadores, mismas semillas por defecto) para que los resultados historicos se reproduzcan.
Anadido: bootstrap por bloques / por dia (los trades de un mismo dia o semana no son independientes).
"""
from __future__ import annotations

import numpy as np


def pf(r, sin_perdidas: float = np.inf) -> float:
    """Profit factor = ganancias / perdidas. Sin perdidas: `sin_perdidas` (inf si hay ganancia, nan si no hay nada)."""
    r = np.asarray(r, float)
    if len(r) == 0:
        return float("nan")
    g, p = r[r > 0].sum(), -r[r < 0].sum()
    if p > 0:
        return float(g / p)
    if np.isinf(sin_perdidas):
        return float(np.inf) if g > 0 else float("nan")
    return float(sin_perdidas)


def _pf_matriz(x: np.ndarray, sin_perdidas: float) -> np.ndarray:
    g = np.where(x > 0, x, 0).sum(1)
    p = -np.where(x < 0, x, 0).sum(1)
    return np.where(p > 0, g / np.where(p > 0, p, 1), sin_perdidas)


def bootstrap_iid(r, n: int = 5000, seed: int = 7, sin_perdidas: float = np.inf) -> dict:
    """Bootstrap iid de trades. IC90 = percentiles 5 y 95. Devuelve PF y expectancy (R/trade)."""
    r = np.asarray(r, float)
    if len(r) < 5:
        return dict(pf_lo=np.nan, pf_med=np.nan, pf_hi=np.nan, exp_lo=np.nan, exp_hi=np.nan)
    rng = np.random.default_rng(seed)
    x = r[rng.integers(0, len(r), (n, len(r)))]
    v = _pf_matriz(x, sin_perdidas)
    e = x.mean(axis=1)
    return dict(pf_lo=float(np.percentile(v, 5)), pf_med=float(np.percentile(v, 50)), pf_hi=float(np.percentile(v, 95)),
                exp_lo=float(np.percentile(e, 5)), exp_hi=float(np.percentile(e, 95)))


def bootstrap_bloques(r, grupos=None, n: int = 5000, seed: int = 7, bloque: int = 20,
                      sin_perdidas: float = np.inf) -> dict:
    """Bootstrap que respeta la dependencia.

    - Con `grupos` (p.ej. fecha de cada trade): se remuestrean GRUPOS completos (todos los trades de un dia juntos).
    - Sin `grupos`: bootstrap de bloques moviles de `bloque` trades consecutivos (el orden de `r` debe ser cronologico).
    Con trades independientes da un IC parecido al iid; con agrupacion/autocorrelacion el IC es mas ancho (mas honesto).
    """
    r = np.asarray(r, float)
    if len(r) < 5:
        return dict(pf_lo=np.nan, pf_med=np.nan, pf_hi=np.nan, exp_lo=np.nan, exp_hi=np.nan)
    rng = np.random.default_rng(seed)
    pfs, exps = np.empty(n), np.empty(n)
    if grupos is not None:
        grupos = np.asarray(grupos)
        _, inv = np.unique(grupos, return_inverse=True)
        idx_g = [np.flatnonzero(inv == k) for k in range(inv.max() + 1)]
        ng = len(idx_g)
        for i in range(n):
            ids = rng.integers(0, ng, ng)
            x = r[np.concatenate([idx_g[k] for k in ids])]
            pfs[i], exps[i] = pf(x, sin_perdidas), x.mean()
    else:
        nr, b = len(r), max(1, min(bloque, len(r)))
        nb = int(np.ceil(nr / b))
        for i in range(n):
            st = rng.integers(0, nr - b + 1, nb)
            x = np.concatenate([r[s:s + b] for s in st])[:nr]
            pfs[i], exps[i] = pf(x, sin_perdidas), x.mean()
    ok = ~np.isnan(pfs)
    return dict(pf_lo=float(np.percentile(pfs[ok], 5)), pf_med=float(np.percentile(pfs[ok], 50)),
                pf_hi=float(np.percentile(pfs[ok], 95)),
                exp_lo=float(np.percentile(exps, 5)), exp_hi=float(np.percentile(exps, 95)))


def maxdd(r) -> float:
    """Maximo drawdown de la curva acumulada en R."""
    r = np.asarray(r, float)
    c = np.cumsum(r)
    return float((np.maximum.accumulate(np.r_[0, c])[1:] - c).max()) if len(r) else 0.0


def mc_dd_iid(r, n: int = 5000, seed: int = 11, riesgo: float = 0.005):
    """Monte Carlo iid del max DD (% del capital con `riesgo` por trade). Devuelve (p50, p95)."""
    r = np.asarray(r, float)
    rng = np.random.default_rng(seed)
    d = np.array([maxdd(r[rng.integers(0, len(r), len(r))]) for _ in range(n)]) * riesgo * 100
    return float(np.percentile(d, 50)), float(np.percentile(d, 95))


def monte_carlo_dd_bloques(R, bloque: int = 20, n_paths: int = 5000, seed: int = 7) -> dict:
    """Monte Carlo por bloques: DD (en R) y racha perdedora maxima, real vs simulada."""
    R = np.asarray(R, float)
    rng = np.random.default_rng(seed)
    n = len(R)
    if n < bloque * 2:
        return {}

    def racha(x):
        r = m = 0
        for v in x:
            r = r + 1 if v < 0 else 0
            m = max(m, r)
        return m

    dds, rachas = [], []
    nb = int(np.ceil(n / bloque))
    for _ in range(n_paths):
        st = rng.integers(0, n - bloque + 1, size=nb)
        x = np.concatenate([R[s:s + bloque] for s in st])[:n]
        eq = np.cumsum(x)
        dds.append((np.maximum.accumulate(eq) - eq).max())
        rachas.append(racha(x))
    eq0 = np.cumsum(R)
    return dict(dd_real=(np.maximum.accumulate(eq0) - eq0).max(), dd_p50=np.percentile(dds, 50),
                dd_p95=np.percentile(dds, 95), racha_real=racha(R), racha_p95=np.percentile(rachas, 95))


def resumen_r(r, n_boot: int = 5000, seed: int = 7, sin_perdidas: float = np.inf, grupos=None) -> dict:
    """Resumen estandar de una serie R neta: n, win, PF, expR, IC90 (iid y, si hay `grupos`, por dia), max DD."""
    r = np.asarray(r, float)
    if len(r) == 0:
        return dict(n=0)
    b = bootstrap_iid(r, n_boot, seed, sin_perdidas)
    out = dict(n=len(r), win=float((r > 0).mean() * 100), PF=pf(r, sin_perdidas), expR=float(r.mean()),
               pf_lo=b["pf_lo"], pf_hi=b["pf_hi"], exp_lo=b["exp_lo"], exp_hi=b["exp_hi"], DD_R=maxdd(r))
    if grupos is not None:
        bb = bootstrap_bloques(r, grupos, n_boot, seed, sin_perdidas=sin_perdidas)
        out.update(pf_lo_dia=bb["pf_lo"], pf_hi_dia=bb["pf_hi"])
    return out
