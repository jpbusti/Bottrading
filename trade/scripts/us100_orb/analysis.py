"""Reportes y metricas de us100_orb sobre trades ya simulados (no corre backtests). Usa validacion/ para todo el calculo.

Entrada: DataFrame de simular_trades (una fila por trade x combo, columnas fecha, anio, combo, R).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from validacion import pf_inference as pi  # noqa: E402
from validacion.atr_grid import excluir_cada_anio, rejilla  # noqa: E402


def r_fn(df: pd.DataFrame) -> np.ndarray:
    return df.R.values


def central(trades: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return trades[trades.combo == tuple(cfg["riesgo"]["combo_central"])]


def resumen_central(trades: pd.DataFrame, cfg: dict) -> dict:
    """PF neto, IC90 (por dia) del PF, n trades, max DD (R y % de cuenta con riesgo_por_trade_pct) y PF por anio."""
    t = central(trades, cfg)
    if len(t) == 0:
        return dict(n=0)
    res = pi.resumen_r(t.R.values, grupos=t.fecha.values)
    res["DD_pct"] = res["DD_R"] * cfg["riesgo"]["riesgo_por_trade_pct"]
    por_anio = t.groupby("anio").apply(lambda g: pd.Series(dict(n=len(g), PF=pi.pf(g.R.values), expR=g.R.mean())), include_groups=False)
    res["por_anio"] = por_anio
    return res


def robustez(trades: pd.DataFrame, cfg: dict) -> dict:
    """Rejilla k x m (9 puntos) y sensibilidad temporal (excluir cada anio) sobre el combo central."""
    return dict(rejilla=rejilla(trades, r_fn, cfg["riesgo"]["k_sl"], cfg["riesgo"]["m_tp"], cfg["aprobacion"]["pf_min"]),
                sin_anio=excluir_cada_anio(central(trades, cfg), r_fn, cfg["validacion"]["fragilidad_umbral_dpf"]))


def criterios(res: dict, rob: dict, placebos_ok: bool | None, cfg: dict) -> dict:
    """Criterios de docs/PREREGISTRO_US100_ORB.md. placebos_ok=None si aun no se corrieron (el veredicto queda incompleto)."""
    a = cfg["aprobacion"]
    c = {
        "PF_neto>=min": bool(res.get("PF", 0) >= a["pf_min"]),
        "IC90_PF_inferior>1": bool(res.get("pf_lo_dia", 0) > a["ic90_pf_inferior_min"]),
        "trades>=min": bool(res.get("n", 0) >= a["trades_min"]),
        "DD<max": bool(res.get("DD_pct", np.inf) < a["max_dd_pct"]),
        "rejilla_robusta": bool(rob["rejilla"]["robusta"]),
        "placebos": placebos_ok,
    }
    c["APROBADA"] = bool(all(v is True for v in c.values())) if placebos_ok is not None else None
    return c


def imprimir(res: dict, rob: dict, crit: dict) -> None:
    if res.get("n", 0) == 0:
        print("sin trades")
        return
    print(f"n={res['n']} win={res['win']:.1f}% PF={res['PF']:.3f} IC90 PF=[{res['pf_lo_dia']:.3f},{res['pf_hi_dia']:.3f}] "
          f"expR={res['expR']:.3f} maxDD={res['DD_R']:.1f}R ({res['DD_pct']:.1f}%)")
    print(res["por_anio"].round(3).to_string())
    print("\nRejilla k x m:\n", rob["rejilla"]["tabla"].round(3).to_string(), f"\nrobusta={rob['rejilla']['robusta']}")
    print("\nExcluyendo cada anio:\n", rob["sin_anio"].round(3).to_string())
    print("\nCriterios:", crit)
