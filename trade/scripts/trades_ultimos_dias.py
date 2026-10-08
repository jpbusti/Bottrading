"""
DETALLE DE TRADES PDH/PDL (SL25 / TP40 / 1 trade al día) en las últimas N sesiones de Databento,
para contrastar uno a uno con el trading manual, y comparación con el backtest del año completo.

Uso (desde la raíz):  python -m scripts.trades_ultimos_dias [N_SESIONES]   (por defecto 15)
"""
import sys
import types

import numpy as np
import pandas as pd

from config import config as cfg
from src.datos import cargar_datos
from scripts import pdh_pdl_lab as lab

SL, TP, MAX_TRADES, HORA = 25, 40, 1, "15:00"
PARAMS = {"sl_puntos": SL, "tp_puntos": TP, "max_trades_dia": MAX_TRADES, "modo_salida": "TP_FIJO",
          "trailing_puntos": 0, "hora_ultima_entrada": HORA}


def hhmm(minutos):
    return f"{int(minutos) // 60:02d}:{int(minutos) % 60:02d}"


def resumen(trades, n_dias):
    """Ganancias, pérdidas, PF y demás a partir de los trades del motor."""
    netos = trades["Neto_USD"].to_numpy()
    gan, per = netos[netos > 0].sum(), -netos[netos <= 0].sum()
    return {"Dias": n_dias, "Trades": len(netos), "Ganadores": int((netos > 0).sum()),
            "Perdedores": int((netos <= 0).sum()), "Win_Rate": (netos > 0).mean() * 100,
            "Ganancias": gan, "Perdidas": per, "Neto": netos.sum(),
            "PF": gan / per if per > 0 else float("inf"), "Expectancy": netos.mean(),
            "Puntos_medios": trades["Puntos"].mean()}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    c = types.SimpleNamespace(**{k: v for k, v in vars(cfg).items() if k.isupper()})
    c.CSV_PREFIJO, c.INTERVALO, c.TIINGO_API_KEY = "NQ_databento", "5m", ""
    df = cargar_datos(c)
    if df is None:
        sys.exit("ERROR: sin datos")

    # Backtest del año completo (referencia)
    dias_all = lab.preparar_dias(df)
    tr_all, _ = lab.backtest_completo(dias_all, PARAMS)
    res_all = resumen(tr_all, len(dias_all))

    # Últimas n sesiones (+1 sesión previa que solo aporta PDH/PDL), balance inicial limpio
    fechas = sorted(df["Date"].unique())
    sub = df[df["Date"].isin(fechas[-(n + 1):])]
    dias = lab.preparar_dias(sub)
    tr, _ = lab.backtest_completo(dias, PARAMS)
    print(f"\nÚltimas {len(dias)} sesiones: {dias[0]['fecha']} -> {dias[-1]['fecha']} "
          f"(datos hasta {fechas[-1]}) | SL{SL} TP{TP} {MAX_TRADES} trade/día | spread {lab.SPREAD_PUNTOS} pts "
          f"(LONG entra al ask) | hora NY")

    # --- Todos los toques detectados por día y cuál se operó ---
    print("\n" + "=" * 100)
    print(" TOQUES DE PDH/PDL DETECTADOS (cierre de la vela que toca = precio de señal)")
    print("=" * 100)
    for d in dias:
        tdia = tr[tr["Fecha"] == d["fecha"]] if not tr.empty else tr
        op_min = set(tdia["Entrada_Min"]) if len(tdia) else set()
        print(f"\n{d['fecha']}  PDH {d['pdh']:.2f} | PDL {d['pdl']:.2f} | rango del día {d['l'].min():.2f}-{d['h'].max():.2f}")
        if len(d["sig_idx"]) == 0:
            print("   (sin toques)")
        for lado in (-1, 1):   # un renglón por nivel: primer toque + velas adicionales dentro de la zona
            idx = [i for i, dr in zip(d["sig_idx"], d["sig_dir"]) if dr == lado]
            if not idx:
                continue
            i = idx[0]
            nivel = d["pdh"] if lado == -1 else d["pdl"]
            tomado = "OPERADO" if int(d["min"][i]) in op_min else "no operado (ya hubo trade ese día)"
            extra = f" (+{len(idx) - 1} velas más en la zona)" if len(idx) > 1 else ""
            print(f"   {hhmm(d['min'][i])}  1er toque {'PDH' if lado == -1 else 'PDL'} {nivel:.2f}  "
                  f"({'SHORT' if lado == -1 else 'LONG '}) cierre {d['c'][i]:.2f}{extra} -> {tomado}")

    # --- Trades ---
    print("\n" + "=" * 100)
    print(" TRADES EJECUTADOS")
    print("=" * 100)
    if tr.empty:
        print("Sin trades en el periodo.")
        return
    filas = []
    por_fecha = {d["fecha"]: d for d in dias}
    for _, t in tr.iterrows():
        d = por_fecha[t["Fecha"]]
        i = int(np.where(d["min"] == t["Entrada_Min"])[0][0])
        largo = t["Dir"] == "LONG"
        entrada = d["c"][i] + (lab.SPREAD_PUNTOS if largo else 0.0)
        salida = entrada + t["Puntos"] if largo else entrada - t["Puntos"]
        sl_niv = entrada - SL if largo else entrada + SL
        tp_niv = entrada + TP if largo else entrada - TP
        filas.append({"Fecha": t["Fecha"], "Dir": t["Dir"], "Hora_ent": hhmm(t["Entrada_Min"]),
                      "Entrada": round(entrada, 2), "SL": round(sl_niv, 2), "TP": round(tp_niv, 2),
                      "Hora_sal": hhmm(t["Salida_Min"]), "Salida": round(salida, 2), "Motivo": t["Motivo"],
                      "Puntos": round(t["Puntos"], 2), "Lotes": t["Lotes"], "Neto_USD": round(t["Neto_USD"], 2)})
    out = pd.DataFrame(filas)
    print(out.to_string(index=False))

    r = resumen(tr, len(dias))
    print("\n" + "=" * 100)
    print(" RESUMEN: últimas sesiones vs año completo")
    print("=" * 100)
    print(f" {'':<22}{'Últimas ' + str(len(dias)) + ' ses.':>16}{'Año (' + str(res_all['Dias']) + ' ses.)':>18}")
    for k, nombre, fmt in [("Trades", "Trades", "{:.0f}"), ("Ganadores", "Ganadores", "{:.0f}"),
                           ("Perdedores", "Perdedores", "{:.0f}"), ("Win_Rate", "Win Rate %", "{:.1f}"),
                           ("Ganancias", "Total ganancias USD", "{:.2f}"), ("Perdidas", "Total pérdidas USD", "{:.2f}"),
                           ("Neto", "Neto USD", "{:+.2f}"), ("PF", "Profit Factor", "{:.2f}"),
                           ("Expectancy", "Expectancy USD/trade", "{:+.2f}"), ("Puntos_medios", "Puntos medios/trade", "{:+.2f}")]:
        print(f" {nombre:<22}{fmt.format(r[k]):>16}{fmt.format(res_all[k]):>18}")
    print(f"\n Motivos de salida (últimas sesiones): {tr['Motivo'].value_counts().to_dict()}")
    print(f" Motivos de salida (año): {tr_all['Motivo'].value_counts().to_dict()}")
    out.to_csv(f"{cfg.DIR_RESULTADOS_CSV}\\trades_ultimos_{len(dias)}_dias.csv", index=False)


if __name__ == "__main__":
    main()
