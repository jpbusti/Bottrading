"""
PDH/PDL SIN GAPS por franja horaria (hora de Nueva York), Databento 5m, SL25 / TP40 / 1 trade por día.

Se carga la sesión desde las 08:30 (el CSV trae también las velas previas a la apertura), pero PDH/PDL
siguen siendo el máximo/mínimo de la sesión REGULAR (09:30-16:00) del día anterior.

Cada franja filtra la HORA DE LA SEÑAL (se opera como mucho 1 vez al día, dentro de la franja).
Regla de gap: se descarta el día si el precio de referencia abre a más de 50 pts fuera del rango previo.
La referencia es la apertura de la franja (sin mirar el futuro): 08:30 y 09:00 para las franjas de
pre-apertura; para MID y LATE, la apertura regular de las 09:30.
Las franjas se solapan a propósito (TEMPRANO ⊂ CORE ⊂ APERTURA ... ), no son independientes.

Uso (desde la raíz):  python -m scripts.horarios_sin_gaps
"""
import os
import sys
import types

import numpy as np
import pandas as pd

from config import config as cfg
from src.datos import cargar_datos
from src.estrategias.pdh_pdl import EstrategiaPDH_PDL_SinGap
from src.motor.motor_estrategias import DatosPreparados, dias_con_senales, params_tp_fijo
from scripts import pdh_pdl_lab as lab

SL, TP, MAX_TRADES, MAX_GAP = 25, 40, 1, 50.0
# (nombre, inicio señales, fin señales, hora de referencia para medir el gap)
FRANJAS = [
    ("TEMPRANO", "09:00", "10:00", "09:00"),
    ("CORE", "09:00", "10:30", "09:00"),
    ("APERTURA", "08:30", "10:30", "08:30"),
    ("MID", "10:30", "14:00", "09:30"),
    ("LATE", "14:00", "16:00", "09:30"),
    ("(ref) SESION 09:30-16:00", "09:30", "16:00", "09:30"),
]


def pf(netos):
    g, p = netos[netos > 0].sum(), -netos[netos <= 0].sum()
    return g / p if p > 0 else float("inf")


def ic_pf(netos, n=2000, semilla=7):
    """Intervalo 90 % del PF por bootstrap de trades (numpy): da idea de cuánto ruido hay."""
    rng = np.random.default_rng(semilla)
    pfs = [pf(rng.choice(netos, len(netos))) for _ in range(n)]
    pfs = np.clip(pfs, 0, 10)
    return np.percentile(pfs, 5), np.percentile(pfs, 95)


def minutos(df):
    return (df.index.hour * 60 + df.index.minute).to_numpy()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    c = types.SimpleNamespace(**{k: v for k, v in vars(cfg).items() if k.isupper()})
    c.CSV_PREFIJO, c.INTERVALO, c.TIINGO_API_KEY, c.HORA_INICIO = "NQ_databento", "5m", "", "08:30"
    df = cargar_datos(c)   # sesión extendida 08:30-16:00 NY
    if df is None:
        sys.exit("ERROR: sin datos")

    # PDH/PDL = extremos de la sesión REGULAR del día anterior (no de las velas previas a la apertura)
    rth = df.between_time("09:30", "16:00", inclusive="left")
    diario = rth.groupby("Date").agg(H=("High", "max"), L=("Low", "min"))
    df["PDH"] = df["Date"].map(diario["H"].shift(1))
    df["PDL"] = df["Date"].map(diario["L"].shift(1))

    prep = DatosPreparados(df, "5m")
    params = params_tp_fijo(SL, TP, MAX_TRADES, "15:55")   # el límite de entrada lo marca cada franja
    n_is = int(len(prep.dias) * 0.60)
    est = EstrategiaPDH_PDL_SinGap(MAX_GAP)
    mins = minutos(df)
    print(f"\nSesiones: {len(prep.dias)} ({prep.dias[0]['fecha']} -> {prep.dias[-1]['fecha']}) | "
          f"SL{SL} TP{TP} {MAX_TRADES} trade/día | gap > {MAX_GAP:.0f} pts | datos 08:30-16:00 NY")

    filas = []
    for nombre, ini, fin, ref in FRANJAS:
        # El gap se mide con la apertura de la franja: df recortado desde `ref` (1ª vela = referencia)
        sub = df[mins >= lab.a_minutos(ref)]
        senales = [s for s in est.generar_senales(sub)
                   if lab.a_minutos(ini) <= s.ts.hour * 60 + s.ts.minute < lab.a_minutos(fin)]
        dias = dias_con_senales(prep, senales)
        tr, m = lab.backtest_completo(dias, params)
        fila = {"Franja": nombre, "Horario": f"{ini}-{fin}", "Ref_gap": ref}
        if m is None:
            filas.append({**fila, "Trades": 0})
            continue
        netos = tr["Neto_USD"].to_numpy()
        lo, hi = ic_pf(netos)
        _, m_is = lab.backtest_completo(dias[:n_is], params)
        _, m_oos = lab.backtest_completo(dias[n_is:], params)
        fila.update({"Trades": m["Total_Trades"], "Win_Rate": m["Win_Rate"], "PF": m["Profit_Factor"],
                     "PF_IC90_bajo": lo, "PF_IC90_alto": hi, "Neto_USD": m["Neto_USD"],
                     "Max_DD_Pct": m["Max_DD_Pct"], "Sharpe": m["Sharpe_Ratio"],
                     "Trades_IS": m_is["Total_Trades"] if m_is else 0, "PF_IS": m_is["Profit_Factor"] if m_is else np.nan,
                     "Trades_OOS": m_oos["Total_Trades"] if m_oos else 0, "PF_OOS": m_oos["Profit_Factor"] if m_oos else np.nan})
        filas.append(fila)

    res = pd.DataFrame(filas)
    os.makedirs(cfg.DIR_RESULTADOS_CSV, exist_ok=True)
    ruta = os.path.join(cfg.DIR_RESULTADOS_CSV, "pdh_pdl_sin_gaps_por_horario.csv")
    res.to_csv(ruta, index=False)

    print("\n" + "=" * 112)
    print(" PDH/PDL SIN GAPS POR FRANJA HORARIA (hora NY)")
    print("=" * 112)
    cols = ["Franja", "Horario", "Trades", "Win_Rate", "PF", "PF_IC90_bajo", "PF_IC90_alto", "Neto_USD",
            "Max_DD_Pct", "Sharpe"]
    print(res[cols].round(2).to_string(index=False))
    print("\n Walk-forward 60/40 por franja:")
    print(res[["Franja", "Trades_IS", "PF_IS", "Trades_OOS", "PF_OOS"]].round(2).to_string(index=False))

    reales = res[~res["Franja"].str.startswith("(ref)") & (res["Trades"] > 0)].sort_values("PF", ascending=False)
    mejor = reales.iloc[0]
    print("\n" + "=" * 112)
    print(f" Mayor PF: {mejor['Franja']} ({mejor['Horario']}) PF {mejor['PF']:.2f} con {int(mejor['Trades'])} trades "
          f"| IC90 del PF [{mejor['PF_IC90_bajo']:.2f}, {mejor['PF_IC90_alto']:.2f}] | PF OOS {mejor['PF_OOS']:.2f}")
    print("=" * 112)
    print(f"\nCSV: {ruta}")


if __name__ == "__main__":
    main()
