"""Placebos obligatorios: nivel (D-N), timing aleatorio, direccion invertida, con N sorteos y p-valor.

Este modulo es agnostico del motor: recibe funciones que corren el backtest en modo placebo y devuelven la serie R neta.
Contrato:  fn(...) -> np.ndarray de R netas (un valor por trade).
p-valor = (1 + #sorteos con PF >= PF_real) / (1 + N): probabilidad de igualar o superar a la estrategia real por azar.
Una estrategia solo supera un placebo si PF_real > PF_placebo (determinista) o p <= alpha (aleatorio).
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from .pf_inference import pf


def p_valor(pf_real: float, pf_placebos, minimo_cola: bool = True) -> float:
    a = np.asarray([x for x in pf_placebos if np.isfinite(x)], float)
    if len(a) == 0:
        return float("nan")
    return float((1 + (a >= pf_real).sum()) / (1 + len(a)))


def placebo_nivel(r_real, r_fn_por_lag: Callable[[int], np.ndarray], lags=(2, 3, 5, 10)) -> dict:
    """Niveles de hace N dias en lugar de los de D-1 (el motor recibe `lag`; en LSR: generar(..., lag=N)).
    Deterministico: sin_info si PF(real) <= PF(placebo)."""
    pr = pf(r_real)
    res = {lag: pf(r_fn_por_lag(lag)) for lag in lags}
    return dict(pf_real=pr, pf_placebo=res, supera=bool(pr > 1.0 and all(pr > v for v in res.values() if np.isfinite(v))),
                peor_placebo=float(max((v for v in res.values() if np.isfinite(v)), default=np.nan)))


def placebo_timing(r_real, r_fn_sorteo: Callable[[int], np.ndarray], n: int = 200, alpha: float = 0.05) -> dict:
    """Entradas en horas aleatorias con la misma gestion (r_fn_sorteo(seed) re-simula con timing aleatorio)."""
    pr = pf(r_real)
    pfs = np.array([pf(r_fn_sorteo(s)) for s in range(n)])
    p = p_valor(pr, pfs)
    return dict(pf_real=pr, pf_placebo_med=float(np.nanmedian(pfs)), pf_placebo_p95=float(np.nanpercentile(pfs, 95)),
                p=p, supera=bool(p <= alpha and pr > 1.0))


def placebo_direccion(r_real, r_invertida) -> dict:
    """Misma senal con la direccion invertida (re-simulada, NO el signo de la R: SL/TP no son simetricos).
    Si el PF invertido es similar o mejor, no hay edge direccional."""
    pr, pi = pf(r_real), pf(r_invertida)
    return dict(pf_real=pr, pf_invertido=pi, supera=bool(pr > pi and pr > 1.0))


def veredicto(res_nivel: dict, res_timing: dict, res_direccion: dict) -> dict:
    """Aprobada solo si supera los tres placebos."""
    ok = dict(nivel=res_nivel["supera"], timing=res_timing["supera"], direccion=res_direccion["supera"])
    return dict(**ok, todos=all(ok.values()))
