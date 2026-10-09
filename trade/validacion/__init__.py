"""Modulo comun de validacion cuantitativa (NQ/ES). Criterios: ver skill trading-methodology."""
from .pf_inference import (bootstrap_bloques, bootstrap_iid, maxdd, mc_dd_iid, monte_carlo_dd_bloques, pf,
                           resumen_r)
from .walkforward import fragilidad, pf_por_fold, walk_forward
from .cost_model import (TABLA_CFD, TABLA_LSR_V1, comparar_brokers_cfd, costo_pts, costo_trade, costo_trade_cfd,
                         estado_verificacion, estado_verificacion_cfd)
from .placebo import p_valor, placebo_direccion, placebo_nivel, placebo_timing, veredicto
from .atr_grid import excluir_cada_anio, rejilla

__all__ = ["pf", "bootstrap_iid", "bootstrap_bloques", "maxdd", "mc_dd_iid", "monte_carlo_dd_bloques", "resumen_r",
           "walk_forward", "fragilidad", "pf_por_fold", "costo_pts", "costo_trade", "TABLA_LSR_V1", "estado_verificacion",
           "TABLA_CFD", "costo_trade_cfd", "comparar_brokers_cfd", "estado_verificacion_cfd", "p_valor",
           "placebo_nivel", "placebo_timing", "placebo_direccion", "veredicto", "rejilla", "excluir_cada_anio"]
