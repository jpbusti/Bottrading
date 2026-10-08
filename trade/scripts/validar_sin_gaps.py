"""
PDH/PDL con filtro de GAPS vs PDH/PDL original, sobre Databento 5m (~365 días), SL25 / TP40 / 1 trade/día.

Regla nueva (EstrategiaPDH_PDL_SinGap): solo se opera el toque que llega DESDE DENTRO del rango del
día anterior, y se descarta el día entero si abre a más de 50 puntos fuera del rango (gap).

Uso (desde la raíz):  python -m scripts.validar_sin_gaps
Salidas: resultados/png/pdh_pdl_gaps_vs_reales.png y resultados/csv/pdh_pdl_gaps_trades.csv
"""
import os
import sys
import types

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import config as cfg
from src.datos import cargar_datos
from src.indicadores import agregar_indicadores
from src.estrategias.pdh_pdl import EstrategiaPDH_PDL, EstrategiaPDH_PDL_SinGap
from src.motor.motor_estrategias import DatosPreparados, preparar_senales, params_tp_fijo
from scripts import pdh_pdl_lab as lab

SL, TP, MAX_TRADES, HORA, MAX_GAP = 25, 40, 1, "15:00", 50.0
UMBRAL_PF = 1.1


def pf(netos):
    g, p = netos[netos > 0].sum(), -netos[netos <= 0].sum()
    return g / p if p > 0 else float("inf")


def resumen(trades, m):
    netos = trades["Neto_USD"].to_numpy()
    return {"Trades": len(netos), "Ganadores": int((netos > 0).sum()), "Perdedores": int((netos <= 0).sum()),
            "Win_Rate": (netos > 0).mean() * 100, "PF": pf(netos), "Neto": netos.sum(),
            "Max_DD": m["Max_DD_Pct"], "Sharpe": m["Sharpe_Ratio"]}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    c = types.SimpleNamespace(**{k: v for k, v in vars(cfg).items() if k.isupper()})
    c.CSV_PREFIJO, c.INTERVALO, c.TIINGO_API_KEY = "NQ_databento", "5m", ""
    df = cargar_datos(c)
    if df is None:
        sys.exit("ERROR: sin datos")
    df = agregar_indicadores(df, c)
    prep = DatosPreparados(df, "5m")
    params = params_tp_fijo(SL, TP, MAX_TRADES, HORA)

    est_old, est_new = EstrategiaPDH_PDL(), EstrategiaPDH_PDL_SinGap(MAX_GAP)
    dias_old = preparar_senales(prep, est_old)
    dias_new = preparar_senales(prep, est_new)
    tr_old, m_old = lab.backtest_completo(dias_old, params)
    tr_new, m_new = lab.backtest_completo(dias_new, params)
    r_old, r_new = resumen(tr_old, m_old), resumen(tr_new, m_new)

    # --- Trades del backtest ORIGINAL que el filtro habría rechazado, con su motivo ---
    validas = {(s.ts.date(), s.ts.hour * 60 + s.ts.minute) for s in est_new.generar_senales(df)}
    gap_dia = pd.Series(est_new.mascaras(df)[2], index=df.index).groupby(df["Date"]).first()
    tr_old = tr_old.copy()
    tr_old["Aceptado"] = [(f, e) in validas for f, e in zip(tr_old["Fecha"], tr_old["Entrada_Min"])]
    tr_old["Motivo_Rechazo"] = np.where(tr_old["Aceptado"], "",
                                        np.where(tr_old["Fecha"].map(gap_dia).fillna(False),
                                                 f"gap (abre >{MAX_GAP:.0f} pts fuera)", "no venía de dentro"))
    rech = tr_old[~tr_old["Aceptado"]]
    n_gap_dias = int(gap_dia.reindex([d["fecha"] for d in prep.dias]).sum())

    print("\n" + "=" * 86)
    print(f" PDH/PDL sin gaps | Databento 5m | {len(prep.dias)} sesiones | SL{SL} TP{TP} {MAX_TRADES} trade/día")
    print("=" * 86)
    print(f" Días con gap (> {MAX_GAP:.0f} pts fuera del rango previo): {n_gap_dias} de {len(prep.dias)}")
    print(f" Trades del backtest original rechazados por el filtro: {len(rech)} de {len(tr_old)} "
          f"({(rech['Motivo_Rechazo'].str.startswith('gap')).sum()} por gap, "
          f"{(rech['Motivo_Rechazo'] == 'no venía de dentro').sum()} por no venir de dentro)")
    print(f"\n {'':<16}{'Original':>12}{'Sin gaps':>12}{'Rechazados':>13}")
    nr = rech["Neto_USD"].to_numpy()
    filas = [("Trades", r_old["Trades"], r_new["Trades"], len(rech), "{:.0f}"),
             ("Ganadores", r_old["Ganadores"], r_new["Ganadores"], int((nr > 0).sum()), "{:.0f}"),
             ("Perdedores", r_old["Perdedores"], r_new["Perdedores"], int((nr <= 0).sum()), "{:.0f}"),
             ("Win Rate %", r_old["Win_Rate"], r_new["Win_Rate"], (nr > 0).mean() * 100 if len(nr) else np.nan, "{:.1f}"),
             ("Profit Factor", r_old["PF"], r_new["PF"], pf(nr) if len(nr) else np.nan, "{:.2f}"),
             ("Neto USD", r_old["Neto"], r_new["Neto"], nr.sum(), "{:+.2f}"),
             ("Max DD %", r_old["Max_DD"], r_new["Max_DD"], np.nan, "{:.1f}"),
             ("Sharpe", r_old["Sharpe"], r_new["Sharpe"], np.nan, "{:.2f}")]
    for nombre, a, b, r, fmt in filas:
        print(f" {nombre:<16}{fmt.format(a):>12}{fmt.format(b):>12}{fmt.format(r) if pd.notna(r) else '-':>13}")

    # --- IS / OOS del filtro ---
    n_is = int(len(prep.dias) * 0.60)
    print("\n Walk-forward 60/40 de la versión sin gaps:")
    for et, d in (("IS", dias_new[:n_is]), ("OOS", dias_new[n_is:])):
        t, m = lab.backtest_completo(d, params)
        if m:
            print(f"   {et:<4} {len(d)} días | trades {m['Total_Trades']:>3} | Win {m['Win_Rate']:.1f} % | "
                  f"PF {m['Profit_Factor']:.2f} | neto {m['Neto_USD']:+.2f} USD | DD {m['Max_DD_Pct']:.1f} %")

    # --- Gráfico ---
    fig, ax = plt.subplots(1, 3, figsize=(17, 5))
    def equity(t):
        return np.concatenate([[lab.BALANCE_INICIAL], lab.BALANCE_INICIAL + t["Neto_USD"].cumsum().to_numpy()])
    ax[0].plot(equity(tr_old), label=f"Original ({len(tr_old)} trades, PF {r_old['PF']:.2f})", color="gray")
    ax[0].plot(equity(tr_new), label=f"Sin gaps ({len(tr_new)} trades, PF {r_new['PF']:.2f})", color="tab:blue")
    ax[0].plot(equity(rech), label=f"Rechazados ({len(rech)} trades, PF {pf(nr):.2f})", color="tab:red")
    ax[0].axhline(lab.BALANCE_INICIAL, color="k", lw=0.6, ls="--")
    ax[0].set(title="Curva de equity (por trade)", xlabel="Nº de trade", ylabel="Balance USD")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)

    # Panel 2: resultados por grupo (ganadores / perdedores)
    grupos = {"Trades reales\n(sin gaps)": tr_new["Neto_USD"].to_numpy(), "Gaps / rechazados": nr}
    x = np.arange(len(grupos))
    gan = [(v > 0).sum() for v in grupos.values()]
    per = [(v <= 0).sum() for v in grupos.values()]
    ax[1].bar(x - 0.2, gan, 0.4, label="Ganadores", color="tab:green")
    ax[1].bar(x + 0.2, per, 0.4, label="Perdedores", color="tab:red")
    for i, v in enumerate(grupos.values()):
        ax[1].text(i, max(gan[i], per[i]) + 2, f"PF {pf(v):.2f}\nneto {v.sum():+.0f} USD", ha="center", fontsize=9)
    ax[1].set_xticks(x, list(grupos))
    ax[1].set(title="Trades reales vs gaps rechazados", ylabel="Nº de trades")
    ax[1].set_ylim(0, max(max(gan), max(per)) * 1.25)
    ax[1].legend(fontsize=8)

    # Panel 3: PnL de cada trade a lo largo del año, coloreado por grupo
    for t, col, nom in ((tr_new, "tab:blue", "Reales"), (rech, "tab:red", "Rechazados")):
        ax[2].scatter(pd.to_datetime(t["Fecha"]), t["Neto_USD"], s=14, color=col, alpha=0.7, label=nom)
    ax[2].axhline(0, color="k", lw=0.6)
    ax[2].set(title="Resultado de cada trade (USD)", ylabel="USD")
    ax[2].legend(fontsize=8)
    ax[2].tick_params(axis="x", rotation=30)
    fig.suptitle(f"PDH/PDL NQ 5m Databento - SL{SL}/TP{TP} - filtro de gaps > {MAX_GAP:.0f} pts", fontsize=12)
    fig.tight_layout()
    os.makedirs(cfg.DIR_RESULTADOS_PNG, exist_ok=True)
    ruta_png = os.path.join(cfg.DIR_RESULTADOS_PNG, "pdh_pdl_gaps_vs_reales.png")
    fig.savefig(ruta_png, dpi=120)
    plt.close(fig)

    out = pd.concat([tr_new.assign(Grupo="real"), rech.drop(columns=["Aceptado"]).assign(Grupo="rechazado")])
    ruta_csv = os.path.join(cfg.DIR_RESULTADOS_CSV, "pdh_pdl_gaps_trades.csv")
    out.to_csv(ruta_csv, index=False)

    # --- Conclusión (reglas del enunciado) ---
    print("\n" + "=" * 86)
    print(f" ¿PF nuevo {r_new['PF']:.2f} > {UMBRAL_PF}?  (original {r_old['PF']:.2f})")
    print("=" * 86)
    if r_new["PF"] > UMBRAL_PF:
        print(" SÍ: el problema era la codificación de los gaps; el filtro recupera el edge.")
    else:
        print(f" NO: el PF sigue por debajo de {UMBRAL_PF}; los gaps no explican la falta de edge.")
    print(f"\nGráfico: {ruta_png}\nCSV: {ruta_csv}")


if __name__ == "__main__":
    main()
