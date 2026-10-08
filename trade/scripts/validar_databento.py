"""
VALIDACIÓN DE LA CONFIG PDH/PDL (SL25 / TP40 / 1 trade al día / TP fijo) con datos de Databento.

Lee data/raw/NQ_databento_5m.csv, divide 60 % IS / 40 % OOS por días, corre el mismo motor del
laboratorio (PDH/PDL, entrada al cierre de la vela de toque) y compara con el resultado previo de
yfinance (resultados/csv/resultados_grid_IS.csv y _OOS.csv, si existen).

Uso (desde la raíz):  python -m scripts.validar_databento
Sesión: el CSV de Databento es de 24 h (Globex); como en todo el proyecto se usa solo la sesión
regular 09:30-16:00 NY, y PDH/PDL son el máximo/mínimo de esa sesión del día anterior.
"""
import os
import sys

import numpy as np
import pandas as pd

from config import config as cfg
from src.datos import cargar_datos
from src.indicadores import agregar_indicadores
from src.estrategias.pdh_pdl import EstrategiaPDH_PDL
from src.motor.motor_estrategias import DatosPreparados, preparar_senales
from scripts import pdh_pdl_lab as lab

# --- Configuración a validar -------------------------------------------------------
STOP_LOSS_PUNTOS = 25
TAKE_PROFIT_PUNTOS = 40
MAX_TRADES_POR_DIA = 1
MODO_SALIDA = "TP_FIJO"
HORA_ULTIMA_ENTRADA = "15:00"   # con 1 trade/día no cambia el resultado (verificado en el grid previo)
PCT_IN_SAMPLE = 0.60
RUTA_CSV = os.path.join(cfg.DIR_RESULTADOS_CSV, "resultados_databento_validation.csv")
COLUMNAS_REQUERIDAS = ["Datetime", "Open", "High", "Low", "Close", "Volume"]


def verificar_columnas(ruta):
    """El CSV debe traer Datetime, Open, High, Low, Close, Volume."""
    cab = pd.read_csv(ruta, nrows=0).columns.tolist()
    faltan = [c for c in COLUMNAS_REQUERIDAS if c not in cab]
    if faltan:
        sys.exit(f"ERROR: faltan columnas {faltan} en {ruta} (hay {cab})")
    print(f"Columnas OK: {cab}")


def metricas_periodo(dias, etiqueta):
    """Backtest de la config en un conjunto de días. Devuelve dict con todas las métricas pedidas."""
    params = {"sl_puntos": STOP_LOSS_PUNTOS, "tp_puntos": TAKE_PROFIT_PUNTOS,
              "max_trades_dia": MAX_TRADES_POR_DIA, "modo_salida": MODO_SALIDA,
              "trailing_puntos": 0, "hora_ultima_entrada": HORA_ULTIMA_ENTRADA}
    trades, m = lab.backtest_completo(dias, params)
    base = {"Periodo": etiqueta, "Dias": len(dias), "Desde": str(dias[0]["fecha"]), "Hasta": str(dias[-1]["fecha"])}
    if m is None:
        return {**base, "Trades": 0}
    netos = trades["Neto_USD"].to_numpy()
    return {**base, "Trades": m["Total_Trades"], "Ganadores": int((netos > 0).sum()),
            "Perdedores": int((netos <= 0).sum()), "Win_Rate_Pct": m["Win_Rate"],
            "Profit_Factor": m["Profit_Factor"], "Retorno_Neto_USD": m["Neto_USD"],
            "Retorno_Pct": m["Retorno_Pct"], "Max_DD_Pct": m["Max_DD_Pct"], "Sharpe": m["Sharpe_Ratio"],
            "Expectancy_USD": m["Expectancy"]}


def referencia_yfinance():
    """Fila IS y OOS del grid previo (yfinance 5m, 60 días) para SL25/TP40/1 trade, o None."""
    ref = {}
    for et in ("IS", "OOS"):
        ruta = os.path.join(cfg.DIR_RESULTADOS_CSV, f"resultados_grid_{et}.csv")
        if not os.path.exists(ruta):
            return None
        d = pd.read_csv(ruta)
        d = d[(d.SL == STOP_LOSS_PUNTOS) & (d.TP == TAKE_PROFIT_PUNTOS) & (d.MaxTrades == MAX_TRADES_POR_DIA)
              & (d.Modo == MODO_SALIDA) & (d.Estado == "ok")]
        if d.empty:
            return None
        f = d.iloc[0]
        ref[et] = {"Trades": int(f.Total_Trades), "Win_Rate_Pct": f.Win_Rate, "Profit_Factor": f.Profit_Factor,
                   "Retorno_Neto_USD": f.Neto_USD, "Max_DD_Pct": f.Max_DD_Pct, "Sharpe": f.Sharpe_Ratio}
    return ref


def imprimir(fila):
    print(f"  Periodo : {fila['Periodo']} ({fila['Dias']} días, {fila['Desde']} -> {fila['Hasta']})")
    if fila["Trades"] == 0:
        print("  Sin trades.")
        return
    print(f"  Trades totales : {fila['Trades']}  (ganadores {fila['Ganadores']} / perdedores {fila['Perdedores']})")
    print(f"  Win Rate       : {fila['Win_Rate_Pct']:.2f} %")
    print(f"  Profit Factor  : {fila['Profit_Factor']:.2f}")
    print(f"  Retorno neto   : {fila['Retorno_Neto_USD']:+.2f} USD ({fila['Retorno_Pct']:+.2f} %)")
    print(f"  Max Drawdown   : {fila['Max_DD_Pct']:.2f} %")
    print(f"  Sharpe         : {fila['Sharpe']:.2f}")
    print(f"  Expectancy     : {fila['Expectancy_USD']:+.2f} USD/trade")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ruta = os.path.join(cfg.DIR_DATOS_RAW, "NQ_databento_5m.csv")
    if not os.path.exists(ruta):
        sys.exit(f"ERROR: no existe {ruta}")
    verificar_columnas(ruta)

    # Carga con el cargador estándar del proyecto (zona NY, sesión regular, sin duplicados)
    import types
    c = types.SimpleNamespace(**{k: v for k, v in vars(cfg).items() if k.isupper()})
    c.CSV_PREFIJO, c.INTERVALO, c.TIINGO_API_KEY = "NQ_databento", "5m", ""
    df = cargar_datos(c)
    if df is None:
        sys.exit("ERROR: no se pudo cargar el CSV")

    # Comprobaciones de calidad rápidas
    sesiones = df.groupby("Date").size()
    print(f"\nCalidad: {len(sesiones)} sesiones; velas/sesión mediana {int(sesiones.median())} "
          f"(78 = completa); sesiones con < 70 velas: {(sesiones < 70).sum()}")
    cierre_d = df.groupby("Date")["Close"].last()
    apert_d = df.groupby("Date")["Open"].first()
    gap = (apert_d / cierre_d.shift(1) - 1).abs().dropna()
    print(f"Gaps cierre->apertura > 2 %: {(gap > 0.02).sum()} (posibles saltos de roll si son muchos)")
    print(f"Volumen cero: {(df['Volume'] == 0).sum()} velas | NaN en OHLC: {df[['Open','High','Low','Close']].isna().sum().sum()}")

    df = agregar_indicadores(df, c)
    prep = DatosPreparados(df, "5m")
    dias = preparar_senales(prep, EstrategiaPDH_PDL())   # días con señales de toque PDH/PDL
    n_is = int(len(dias) * PCT_IN_SAMPLE)
    dias_is, dias_oos = dias[:n_is], dias[n_is:]

    print("\n" + "=" * 78)
    print(f" VALIDACIÓN DATABENTO | PDH/PDL | SL{STOP_LOSS_PUNTOS} TP{TAKE_PROFIT_PUNTOS} "
          f"{MAX_TRADES_POR_DIA} trade/día {MODO_SALIDA}")
    print(f" Costes: spread {lab.SPREAD_PUNTOS} pts + comisión {lab.COMISION_POR_LOTE} USD/lote | "
          f"balance inicial {lab.BALANCE_INICIAL:.0f} USD, riesgo {lab.RIESGO_POR_TRADE_PCT} %/trade")
    print("=" * 78)
    filas = []
    for etiqueta, d in (("COMPLETO", dias), ("IN-SAMPLE (60 %)", dias_is), ("OUT-OF-SAMPLE (40 %)", dias_oos)):
        fila = metricas_periodo(d, etiqueta)
        filas.append(fila)
        print(f"\n--- {etiqueta} ---")
        imprimir(fila)

    # Comparación con yfinance
    ref = referencia_yfinance()
    fis, foos = filas[1], filas[2]
    print("\n" + "=" * 78)
    print(" COMPARACIÓN: Databento (≈1 año) vs yfinance (5m, 60 días)")
    print("=" * 78)
    claves = [("Trades", "Trades", "{:.0f}"), ("Win_Rate_Pct", "Win Rate %", "{:.1f}"),
              ("Profit_Factor", "Profit Factor", "{:.2f}"), ("Retorno_Neto_USD", "Retorno USD", "{:+.2f}"),
              ("Max_DD_Pct", "Max DD %", "{:.2f}"), ("Sharpe", "Sharpe", "{:.2f}")]
    if ref is None:
        print(" (no hay resultados previos de yfinance en resultados/csv para comparar)")
    for et, fila_d in (("IS", fis), ("OOS", foos)):
        print(f"\n {et}:   {'métrica':<14}{'Databento':>12}{'yfinance':>12}")
        for k, nombre, fmt in claves:
            vd = fila_d.get(k, np.nan)
            vy = ref[et][k] if ref else np.nan
            print(f"        {nombre:<14}{fmt.format(vd) if pd.notna(vd) else 'n/d':>12}"
                  f"{fmt.format(vy) if pd.notna(vy) else 'n/d':>12}")
        if ref:
            filas.append({"Periodo": f"{et}_YFINANCE_REF", **{k: ref[et][k] for k, _, _ in claves}})

    # Veredicto
    print("\n" + "=" * 78)
    print(" VEREDICTO")
    print("=" * 78)
    if fis["Trades"] == 0 or foos["Trades"] == 0:
        print(" Sin trades en algún periodo: no se puede validar.")
    else:
        pf_is, pf_oos = fis["Profit_Factor"], foos["Profit_Factor"]
        print(f" PF IS {pf_is:.2f} -> PF OOS {pf_oos:.2f} ({foos['Trades']} trades OOS)")
        if pf_is <= 1:
            print(" La config NO tiene edge ni siquiera in-sample con Databento.")
        elif pf_oos >= 1 and pf_oos >= 0.7 * pf_is:
            print(" El edge se MANTIENE fuera de muestra (PF OOS >= 1 y >= 70 % del IS).")
        elif pf_oos >= 1:
            print(" DEGRADACIÓN: sigue rentable en OOS pero con caída > 30 % del PF.")
        else:
            print(" El edge NO se mantiene: PF OOS < 1 (overfitting / el resultado de yfinance era ruido).")
        if foos["Trades"] < 30:
            print(f" Aviso: {foos['Trades']} trades OOS (< 30): evidencia débil.")
        # Un solo trade/día y SL25/TP40 es una config elegida a posteriori con yfinance (60 días):
        print(" Nota: SL25/TP40 salió de optimizar sobre 60 días de yfinance; estos datos ya son nuevos para ella.")

    os.makedirs(cfg.DIR_RESULTADOS_CSV, exist_ok=True)
    pd.DataFrame(filas).to_csv(RUTA_CSV, index=False)
    print(f"\nCSV: {RUTA_CSV}")


if __name__ == "__main__":
    main()
