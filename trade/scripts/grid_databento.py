"""
GRID SEARCH COMPLETO PDH/PDL sobre Databento (NQ 5m, ~1 año) con walk-forward 60/40.

Reutiliza el motor del laboratorio (generar_combinaciones, grid_search, tablas de robustez).
Grid: SL x TP x MaxTrades (TP_FIJO) + SL x Trailing x MaxTrades (TRAILING), hora límite 15:00.

Uso (desde la raíz):  python -m scripts.grid_databento
Salidas en resultados/csv/: grid_databento_completo.csv, top20_databento.csv, walk_forward_databento.csv
"""
import os
import sys
import types

import numpy as np
import pandas as pd

from config import config as cfg
from src.datos import cargar_datos
from scripts import pdh_pdl_lab as lab

HORAS = ["15:00"]
MIN_TRADES_FIABLE = 30      # para el criterio de salida: exigimos >= 30 trades OOS
UMBRAL_PF_OOS = 1.1         # si el mejor PF OOS < 1.1 -> no operar PDH/PDL
CLAVES = ["SL", "TP", "MaxTrades", "Modo", "Trailing", "HoraLimite"]
COLS_M = ["Total_Trades", "Win_Rate", "Profit_Factor", "Retorno_Pct", "Max_DD_Pct", "Sharpe_Ratio"]


def cargar():
    c = types.SimpleNamespace(**{k: v for k, v in vars(cfg).items() if k.isupper()})
    c.CSV_PREFIJO, c.INTERVALO, c.TIINGO_API_KEY = "NQ_databento", "5m", ""
    df = cargar_datos(c)
    if df is None:
        sys.exit("ERROR: no se pudo cargar data/raw/NQ_databento_5m.csv")
    return df


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    lab.GRID_HORAS = HORAS
    os.makedirs(cfg.DIR_RESULTADOS_CSV, exist_ok=True)

    df = cargar()
    dias = lab.preparar_dias(df)
    n_is = int(len(dias) * lab.PCT_IN_SAMPLE)
    dias_is, dias_oos = dias[:n_is], dias[n_is:]
    print(f"Días simulables: {len(dias)} ({dias[0]['fecha']} -> {dias[-1]['fecha']}) | "
          f"IS {len(dias_is)} días (hasta {dias_is[-1]['fecha']}) | OOS {len(dias_oos)} días (desde {dias_oos[0]['fecha']})")
    combos = lab.generar_combinaciones()
    print(f"Combinaciones: {len(combos)} (TP_FIJO {sum(p['modo_salida'] == 'TP_FIJO' for p in combos)}, "
          f"TRAILING {sum(p['modo_salida'] == 'TRAILING' for p in combos)}) x 3 pasadas (completo, IS, OOS)\n")

    res = lab.grid_search(dias, combos, "Completo")
    res_is = lab.grid_search(dias_is, combos, "IS")
    res_oos = lab.grid_search(dias_oos, combos, "OOS")

    # --- Salidas CSV ---
    res.to_csv(os.path.join(cfg.DIR_RESULTADOS_CSV, "grid_databento_completo.csv"), index=False)
    v = lab.validos(res)
    top20 = v.sort_values("Profit_Factor", ascending=False).head(20)
    top20.to_csv(os.path.join(cfg.DIR_RESULTADOS_CSV, "top20_databento.csv"), index=False)

    top_is = lab.validos(res_is).sort_values("Profit_Factor", ascending=False).head(10)
    wf = top_is[CLAVES + COLS_M].merge(res_oos[CLAVES + COLS_M + ["Estado"]], on=CLAVES,
                                       suffixes=("_IS", "_OOS"), how="left")
    wf.insert(0, "Rank_IS", range(1, len(wf) + 1))
    oos_v = lab.validos(res_oos, lab.MIN_TRADES_OOS).copy()
    oos_v["Rank_OOS_Grid"] = oos_v["Profit_Factor"].rank(ascending=False, method="min")
    wf = wf.merge(oos_v[CLAVES + ["Rank_OOS_Grid"]], on=CLAVES, how="left")
    wf.to_csv(os.path.join(cfg.DIR_RESULTADOS_CSV, "walk_forward_databento.csv"), index=False)

    # --- Reporte ---
    n_ok = (res["Estado"] == "ok").sum()
    print("\n" + "=" * 100)
    print(f" GRID PDH/PDL | NQ Databento 5m | {len(dias)} días | {len(combos)} combinaciones "
          f"(ok {n_ok}, válidas >= {lab.MIN_TRADES_RANKING} trades: {len(v)})")
    print("=" * 100)
    lab.imprimir_top(res, "Profit_Factor", "TOP 10 por PROFIT FACTOR (periodo completo)")
    lab.imprimir_top(res, "Sharpe_Ratio", "TOP 10 por SHARPE")
    lab.imprimir_top(res, "Retorno_Pct", "TOP 10 por RETORNO NETO")
    lab.tabla_robustez(res, "SL", "Robustez por SL (PF promedio acotado a 10)")
    lab.tabla_robustez(res, "MaxTrades", "Comparativa 1 vs 2 vs 3 trades/día")
    lab.tabla_robustez(res, "Modo", "Comparativa TP_FIJO vs TRAILING")
    lab.tabla_robustez(res[res["Modo"] == "TP_FIJO"], "TP", "(extra) Robustez por TP, solo TP_FIJO")
    lab.tabla_robustez(res[res["Modo"] == "TRAILING"], "Trailing", "(extra) Robustez por Trailing")

    # --- Walk-forward ---
    print("\n--- ANÁLISIS IS vs OOS: top 10 In-Sample (por PF) evaluado en Out-of-Sample ---")
    cols = ["Rank_IS"] + CLAVES + ["Total_Trades_IS", "Profit_Factor_IS", "Sharpe_Ratio_IS", "Total_Trades_OOS",
                                   "Profit_Factor_OOS", "Sharpe_Ratio_OOS", "Retorno_Pct_OOS", "Rank_OOS_Grid"]
    print(wf[cols].round(2).to_string(index=False))
    t1 = wf.iloc[0]
    rank1 = t1["Rank_OOS_Grid"]
    print(f"\n Top 1 IS: {lab.describir(t1.rename({'SL': 'SL'}))} | PF IS {t1['Profit_Factor_IS']:.2f} -> "
          f"PF OOS {t1['Profit_Factor_OOS']:.2f} | ranking OOS en el grid: "
          f"{'n/d' if pd.isna(rank1) else int(rank1)} de {len(oos_v)}")
    print(f" ¿Sigue siendo top en OOS? {'SÍ' if pd.notna(rank1) and rank1 <= 10 else 'NO'}")
    print(f" Del top 10 IS, {(wf['Profit_Factor_OOS'] > 1).sum()}/10 tienen PF OOS > 1 y "
          f"{(wf['Profit_Factor_OOS'] >= UMBRAL_PF_OOS).sum()}/10 tienen PF OOS >= {UMBRAL_PF_OOS}.")
    comp = lab.validos(res_is).merge(oos_v[CLAVES + ["Profit_Factor"]], on=CLAVES, suffixes=("_IS", "_OOS"))
    if len(comp) > 5:
        corr = comp["Profit_Factor_IS"].clip(upper=10).corr(comp["Profit_Factor_OOS"].clip(upper=10), method="spearman")
        print(f" Correlación de Spearman PF(IS) vs PF(OOS) en todo el grid: {corr:.2f} "
              "(≈0 o negativa = optimizar en IS no predice el futuro)")

    # --- Criterio de salida ---
    print("\n" + "=" * 100)
    print(" CRITERIO DE SALIDA")
    print("=" * 100)
    oos_fiable = lab.validos(res_oos, MIN_TRADES_FIABLE)
    mejor = oos_fiable.sort_values("Profit_Factor", ascending=False).head(1)
    mejor_oos = mejor["Profit_Factor"].iloc[0] if not mejor.empty else float("nan")
    print(f" Mejor PF OOS de todo el grid (>= {MIN_TRADES_FIABLE} trades OOS): "
          f"{'n/d' if pd.isna(mejor_oos) else f'{mejor_oos:.2f}'}")
    if not mejor.empty:
        m = mejor.iloc[0]
        print(f"   {lab.describir(m)} | max{int(m['MaxTrades'])} | trades OOS {int(m['Total_Trades'])} | "
              f"Win {m['Win_Rate']:.1f} % | Retorno {m['Retorno_Pct']:.1f} % | DD {m['Max_DD_Pct']:.1f} % | "
              f"Sharpe {m['Sharpe_Ratio']:.2f}")
    pf_t1 = t1["Profit_Factor_OOS"]
    print(f" PF OOS de la config elegida en IS (top 1 IS): {pf_t1:.2f}")
    if pd.isna(mejor_oos) or mejor_oos < UMBRAL_PF_OOS:
        print(f"\n >>> CONCLUSIÓN: el mejor PF OOS es < {UMBRAL_PF_OOS} -> NO OPERAR PDH/PDL.")
    else:
        print(f"\n >>> El mejor PF OOS es >= {UMBRAL_PF_OOS}, pero es el MEJOR de {len(oos_fiable)} configs mirando OOS "
              "(sesgo de selección). Lo que cuenta es la config elegida en IS:")
        print(f"     PF OOS del top 1 IS = {pf_t1:.2f} -> "
              f"{'sostiene el edge' if pf_t1 >= UMBRAL_PF_OOS else 'NO sostiene el edge: no operar'}.")
    print("\nCSV: grid_databento_completo.csv, top20_databento.csv, walk_forward_databento.csv en resultados/csv/")


if __name__ == "__main__":
    main()
