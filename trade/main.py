"""
COMPARACIÓN AUTOMÁTICA DE ESTRATEGIAS (PDH/PDL, ORB, VWAP) x FILTROS x PARÁMETROS.

Uso:
    python main.py                          # usa config/config.py (CSV local -> Tiingo -> yfinance)
    python main.py --intervalo 1h           # otra temporalidad (lee data/raw/NQ_1h.csv si existe)
    python main.py --estrategia orb         # pdh_pdl | orb | vwap | all
    python main.py --config mi_config.py    # constantes alternativas
    python main.py --ticker ES=F --intervalo 5m

Cada configuración se evalúa en In-Sample (primer 60 % de los días) y Out-of-Sample (resto).
El ranking se hace SOLO con datos IS; el OOS es el examen: si el edge no se mantiene, es overfitting.
"""
import argparse
import importlib.util
import itertools
import os
import sys
import time
import types

import numpy as np
import pandas as pd

from config import config as config_base
from scripts import pdh_pdl_lab as lab
from src.datos import cargar_datos
from src.indicadores import agregar_indicadores
from src.estrategias.pdh_pdl import EstrategiaPDH_PDL
from src.estrategias.orb import EstrategiaORB
from src.estrategias.vwap import EstrategiaVWAP
from src.estrategias.filtros import crear_filtros
from src.motor.motor_estrategias import DatosPreparados, preparar_senales, backtest_estrategia, params_tp_fijo

METRICAS = ["Total_Trades", "Win_Rate", "Profit_Factor", "Expectancy", "Retorno_Pct",
            "Max_DD_Pct", "Sharpe_Ratio", "Sortino_Ratio"]


def construir_config(args):
    """Copia de config.py con los argumentos de línea de comandos aplicados."""
    cfg = types.SimpleNamespace(**{k: v for k, v in vars(config_base).items() if k.isupper()})
    if args.config:   # archivo alternativo: sus constantes MAYÚSCULAS pisan a las de config/config.py
        spec = importlib.util.spec_from_file_location("config_alternativo", args.config)
        alt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(alt)
        cfg.__dict__.update({k: v for k, v in vars(alt).items() if k.isupper()})
    if args.ticker:
        cfg.TICKER = args.ticker
    if args.intervalo:
        cfg.INTERVALO = args.intervalo
    if args.periodo:
        cfg.PERIODO = args.periodo
    return cfg


def evaluar(dias, params):
    """Métricas del motor del laboratorio, o None si no hubo trades."""
    try:
        _, m = backtest_estrategia(None, None, params, dias=dias)
    except Exception:
        return None
    return m


def comparar(prep, estrategias, filtros, cfg):
    """Grid completo estrategia x filtro x (SL, TP, MaxTrades). Devuelve un DataFrame (una fila por config)."""
    k = cfg.ESCALA_PUNTOS
    combos = [(sl * k, tp * k, mt) for sl, tp, mt in
              itertools.product(cfg.GRID_SL, cfg.GRID_TP, cfg.GRID_MAX_TRADES)]
    n_is = int(len(prep.dias) * cfg.PCT_IN_SAMPLE)
    total = len(estrategias) * len(filtros) * len(combos)
    print(f"Días simulables: {len(prep.dias)} ({prep.dias[0]['fecha']} -> {prep.dias[-1]['fecha']}) | "
          f"IS {n_is} días / OOS {len(prep.dias) - n_is} días")
    print(f"Configuraciones: {len(estrategias)} estrategias x {len(filtros)} filtros x {len(combos)} "
          f"parámetros = {total}")
    filas, hecho, t0 = [], 0, time.time()
    for est in estrategias:
        for flt in filtros:
            dias = preparar_senales(prep, est, flt)
            dias_is, dias_oos = dias[:n_is], dias[n_is:]
            n_senales = int(sum(len(d["sig_idx"]) for d in dias))
            for sl, tp, mt in combos:
                p = params_tp_fijo(sl, tp, mt, cfg.HORA_ULTIMA_ENTRADA)
                fila = {"Estrategia": est.nombre, "Filtro": flt.nombre, "SL": sl, "TP": tp,
                        "MaxTrades": mt, "Senales": n_senales}
                for etiqueta, d in (("IS", dias_is), ("OOS", dias_oos)):
                    m = evaluar(d, p)
                    for c in METRICAS:
                        fila[f"{c}_{etiqueta}"] = m[c] if m else np.nan
                    if not m:
                        fila[f"Total_Trades_{etiqueta}"] = 0
                filas.append(fila)
                hecho += 1
            print(f"  [{hecho}/{total}] {est.nombre:9s} + {flt.nombre:11s} ({time.time() - t0:.0f}s)")
    return pd.DataFrame(filas)


def puntuar_is(res, cfg):
    """Puntaje compuesto (PF, Sharpe, MaxDD; menor = mejor) calculado SOLO con métricas In-Sample."""
    v = res[res["Total_Trades_IS"] >= cfg.MIN_TRADES_IS].copy()
    if v.empty:
        return v
    r_pf = v["Profit_Factor_IS"].rank(ascending=False)
    r_sh = v["Sharpe_Ratio_IS"].rank(ascending=False)
    r_dd = v["Max_DD_Pct_IS"].rank(ascending=True)
    v["Puntaje_IS"] = (r_pf + r_sh + r_dd) / 3
    return v.sort_values("Puntaje_IS")


def veredicto(fila, cfg):
    """¿Se mantiene el edge fuera de muestra?"""
    pf_is, pf_oos, n_oos = fila["Profit_Factor_IS"], fila["Profit_Factor_OOS"], fila["Total_Trades_OOS"]
    if pd.isna(pf_oos) or n_oos < cfg.MIN_TRADES_OOS:
        return "SIN DATOS OOS"
    if pf_is <= 1:
        return "SIN EDGE IS"
    if pf_oos >= 1 and pf_oos >= 0.7 * pf_is:
        return "ROBUSTO" + (" (n<30)" if n_oos < cfg.MIN_TRADES_FIABLE else "")
    if pf_oos >= 1:
        return "DEGRADA"
    return "OVERFITTING"


COLS_VER = ["Estrategia", "Filtro", "SL", "TP", "MaxTrades", "Total_Trades_IS", "Profit_Factor_IS",
            "Total_Trades_OOS", "Win_Rate_OOS", "Profit_Factor_OOS", "Max_DD_Pct_OOS",
            "Sharpe_Ratio_OOS", "Retorno_Pct_OOS", "Veredicto"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Comparación de estrategias intradía")
    ap.add_argument("--ticker", help="ticker de yfinance (por defecto config.TICKER)")
    ap.add_argument("--intervalo", help="5m, 15m, 30m, 1h (por defecto config.INTERVALO)")
    ap.add_argument("--periodo", help="periodo yfinance, ej. 60d (solo fallback)")
    ap.add_argument("--estrategia", choices=["pdh_pdl", "orb", "vwap", "all"], default="all",
                    help="estrategia a evaluar (vwap incluye VWAP y VWAP_inv)")
    ap.add_argument("--config", help="ruta a un archivo de configuración alternativo (.py)")
    args = ap.parse_args()
    cfg = construir_config(args)
    os.makedirs(cfg.CARPETA_RESULTADOS, exist_ok=True)
    os.makedirs(cfg.DIR_DATOS_PROCESADOS, exist_ok=True)

    # a) Datos  b) Indicadores
    df = cargar_datos(cfg)
    if df is None:
        sys.exit("Sin datos: ninguna fuente funcionó.")
    if cfg.ESCALA_PUNTOS != 1.0:   # el spread del laboratorio está en puntos NQ
        lab.SPREAD_PUNTOS *= cfg.ESCALA_PUNTOS
    df = agregar_indicadores(df, cfg)
    df.drop(columns=["Date"]).to_csv(
        os.path.join(cfg.DIR_DATOS_PROCESADOS, f"{cfg.CSV_PREFIJO}_{cfg.INTERVALO}_indicadores.csv"))
    prep = DatosPreparados(df, cfg.INTERVALO)
    if len(prep.dias) < 20:
        sys.exit(f"Solo {len(prep.dias)} días simulables: insuficiente.")

    # c) Todas las estrategias x filtros x parámetros   d) tabla comparativa
    catalogo = {"pdh_pdl": [EstrategiaPDH_PDL()], "orb": [EstrategiaORB(cfg.ORB_MINUTOS)],
                "vwap": [EstrategiaVWAP(), EstrategiaVWAP(invertir=True)]}
    estrategias = [e for lista in catalogo.values() for e in lista] if args.estrategia == "all" \
        else catalogo[args.estrategia]
    filtros = crear_filtros(cfg)
    res = comparar(prep, estrategias, filtros, cfg)
    res["Veredicto"] = res.apply(lambda f: veredicto(f, cfg), axis=1)

    # e) Guardado
    ruta = os.path.join(cfg.CARPETA_RESULTADOS, "comparacion_estrategias.csv")
    res.to_csv(ruta, index=False)
    res.to_csv(os.path.join(cfg.CARPETA_RESULTADOS, f"comparacion_estrategias_{cfg.INTERVALO}.csv"), index=False)

    # f) Resumen
    rank = puntuar_is(res, cfg)
    print("\n" + "=" * 100)
    print(f" COMPARACIÓN DE ESTRATEGIAS | {cfg.TICKER} {cfg.INTERVALO} | {len(res)} configuraciones")
    print("=" * 100)
    if rank.empty:
        print(f"Ninguna configuración alcanza {cfg.MIN_TRADES_IS} trades IS.")
        return
    print("\n--- TOP 5 por puntaje compuesto IS (PF + Sharpe + MaxDD), con su resultado OOS ---")
    print(rank[COLS_VER].head(5).round(2).to_string(index=False))

    print("\n--- WALK-FORWARD por estrategia: mejor config IS -> OOS ---")
    mejores = rank.groupby("Estrategia", sort=False).head(1)
    print(mejores[COLS_VER].round(2).to_string(index=False))

    print("\n--- Resumen global por estrategia (todas las configs con >= "
          f"{cfg.MIN_TRADES_IS} trades IS y >= {cfg.MIN_TRADES_OOS} OOS) ---")
    v = rank[rank["Total_Trades_OOS"] >= cfg.MIN_TRADES_OOS].copy()
    if not v.empty:
        v["PF_IS"] = v["Profit_Factor_IS"].clip(upper=10)
        v["PF_OOS"] = v["Profit_Factor_OOS"].clip(upper=10)
        g = v.groupby("Estrategia").agg(Configs=("PF_OOS", "size"), PF_IS_Med=("PF_IS", "median"),
                                        PF_OOS_Med=("PF_OOS", "median"),
                                        Pct_OOS_PF_mayor_1=("PF_OOS", lambda s: (s > 1).mean() * 100))
        print(g.round(2).to_string())

    # Conclusión
    print("\n" + "=" * 100)
    print(" CONCLUSIÓN")
    print("=" * 100)
    robustas = rank[rank["Veredicto"].str.startswith("ROBUSTO")]
    n_prueb = len(res)
    print(f" Con {n_prueb} configuraciones probadas se esperan ~{n_prueb * 0.05:.0f} 'éxitos' por azar al 5 %.")
    if robustas.empty:
        print(" Ninguna configuración (elegida en IS) mantiene PF>1 en OOS con caída <30 %.")
        print(" => No hay evidencia de edge robusto en estos datos.")
    else:
        b = robustas.iloc[0]
        print(" (Candidata = mejor puntaje IS entre las que superan el OOS. Ojo: filtrar por OOS ya usa ese tramo,")
        print("  así que NO es validación independiente; confírmala con datos nuevos.)")
        print(f" Mejor candidata: {b['Estrategia']} + {b['Filtro']} "
              f"SL{b['SL']:g}/TP{b['TP']:g} max{int(b['MaxTrades'])}")
        print(f"   IS : PF {b['Profit_Factor_IS']:.2f} ({int(b['Total_Trades_IS'])} trades)")
        print(f"   OOS: PF {b['Profit_Factor_OOS']:.2f} ({int(b['Total_Trades_OOS'])} trades) | "
              f"Sharpe {b['Sharpe_Ratio_OOS']:.2f} | MaxDD {b['Max_DD_Pct_OOS']:.1f} %")
        if b["Total_Trades_OOS"] < cfg.MIN_TRADES_FIABLE:
            print(f"   ADVERTENCIA: solo {int(b['Total_Trades_OOS'])} trades OOS (<{cfg.MIN_TRADES_FIABLE}); evidencia débil.")
        print(f" {len(robustas)} de {len(rank)} configs válidas salen ROBUSTAS; con tantas pruebas, "
              "parte de ellas es suerte.")
    print(f"\nResultados completos: {ruta}")


if __name__ == "__main__":
    main()
