import sys
import pandas as pd
import numpy as np
import yfinance as yf

# ==============================================================================
# CONFIGURACIÓN (TODO EDITABLE AQUÍ)
# ==============================================================================
# --- Datos ---
TICKER = "NQ=F"            # Futuros E-mini Nasdaq 100 (similar al NAS100 de MT5)
PERIODO = "1mo"            # Periodo a descargar (5m permite máx. ~60 días)
INTERVALO = "5m"           # Tamaño de vela
DIAS_ANALISIS = 20         # Cuántos días recientes se simulan
ZONA_HORARIA = "America/New_York"

# --- Cuenta y contrato ---
BALANCE_INICIAL = 1000    # Balance inicial en USD
VALOR_POR_PUNTO_POR_LOTE = 10.0   # USD por punto con 1.0 lote (0.10 lotes = $1/punto)
LOTE_MINIMO = 0.01         # Lote mínimo permitido por el broker
PASO_LOTE = 0.01           # Incremento de lote

# --- Costos de operación ---
SPREAD_PUNTOS = 0.5        # Spread en puntos (ASK = BID + spread)
COMISION_POR_LOTE = 3.5    # USD round-turn por lote 1.0

# --- Señal ---
TOLERANCIA_PCT = 0.001     # Zona alrededor de PDH/PDL (0.001 = 0.1%)

# --- Salidas (en puntos) ---
STOP_LOSS_PUNTOS = 20.0
TAKE_PROFIT_PUNTOS = 40.0

# --- Horario (hora de Nueva York) ---
HORA_INICIO = "09:30"          # Inicio de sesión (también para calcular PDH/PDL)
HORA_ULTIMA_ENTRADA = "15:00"  # No abrir trades después de esta hora
HORA_CIERRE = "15:55"          # Cierre forzoso de cualquier trade abierto
HORA_FIN_SESION = "16:00"      # Fin de la sesión usada para PDH/PDL

# --- Múltiples entradas por día ---
MINUTOS_ENTRE_ENTRADAS = 30
MAX_TRADES_POR_DIA = 3

# --- Gestión de riesgo ---
RIESGO_POR_TRADE_PCT = 1.0     # % del balance actual arriesgado por trade
# ==============================================================================


def descargar_datos(ticker=TICKER):
    """Descarga velas de yfinance, filtra la sesión regular. Devuelve None si falla."""
    print(f"Descargando datos de {ticker} ({PERIODO}, velas de {INTERVALO})...")
    try:
        df = yf.download(ticker, period=PERIODO, interval=INTERVALO,
                         progress=False, auto_adjust=False)
    except Exception as e:
        print(f"ERROR: falló la descarga de yfinance: {e}")
        return None

    if df is None or df.empty:
        print("ERROR: yfinance no devolvió datos (revisa conexión o ticker).")
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Unificar zona horaria a Nueva York
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(ZONA_HORARIA)

    # Solo sesión regular [HORA_INICIO, HORA_FIN_SESION)
    df = df.between_time(HORA_INICIO, HORA_FIN_SESION, inclusive="left")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if df.empty:
        print("ERROR: no quedan velas dentro del horario de sesión.")
        return None

    df["Date"] = df.index.date
    return df


def detectar_toques(datos_dia, pdh, pdl):
    """
    Devuelve lista de señales (hora, tipo, precio_señal) de la vela de TOQUE,
    en orden cronológico. SHORT si el High entra en zona PDH, LONG si el Low
    entra en zona PDL. Solo usa información de la propia vela (cierre).
    """
    pdh_zona = pdh * (1 - TOLERANCIA_PCT)
    pdl_zona = pdl * (1 + TOLERANCIA_PCT)
    hora_max = pd.Timestamp(HORA_ULTIMA_ENTRADA).time()

    señales = []
    for ts, vela in datos_dia.iterrows():
        if ts.time() > hora_max:
            break
        if vela["High"] >= pdh_zona:
            señales.append((ts, "SHORT", "VENTA EN TECHO (PDH)", vela["Close"]))
        elif vela["Low"] <= pdl_zona:
            señales.append((ts, "LONG", "COMPRA EN PISO (PDL)", vela["Close"]))
    return señales


def calcular_lotes(balance):
    """Lotes para arriesgar RIESGO_POR_TRADE_PCT del balance con el SL dado."""
    riesgo_usd = balance * RIESGO_POR_TRADE_PCT / 100
    lotes = riesgo_usd / (STOP_LOSS_PUNTOS * VALOR_POR_PUNTO_POR_LOTE)
    lotes = np.floor(lotes / PASO_LOTE) * PASO_LOTE
    return round(max(lotes, LOTE_MINIMO), 2)


def simular_trade(datos_dia, ts_señal, direccion, precio_señal, balance):
    """
    Simula un trade VELA POR VELA a partir de la vela siguiente a la señal.
    Entrada al cierre de la vela de señal con spread:
      LONG  entra al ASK (cierre + spread), sale al BID (precio del dato).
      SHORT entra al BID (cierre), sale al ASK (precio del dato + spread).
    Si una vela toca SL y TP, se asume SL primero (peor caso).
    Si la apertura de la vela ya supera el SL (gap), se ejecuta en la apertura.
    """
    lotes = calcular_lotes(balance)
    hora_cierre = pd.Timestamp(HORA_CIERRE).time()

    if direccion == "LONG":
        entrada = precio_señal + SPREAD_PUNTOS
        sl = entrada - STOP_LOSS_PUNTOS
        tp = entrada + TAKE_PROFIT_PUNTOS
    else:
        entrada = precio_señal
        sl = entrada + STOP_LOSS_PUNTOS
        tp = entrada - TAKE_PROFIT_PUNTOS

    posteriores = datos_dia.loc[datos_dia.index > ts_señal]
    motivo, salida, ts_salida = None, None, None

    for ts, v in posteriores.iterrows():
        if direccion == "LONG":
            apertura, maximo, minimo = v["Open"], v["High"], v["Low"]
            if apertura <= sl:
                motivo, salida = "SL (gap)", apertura
            elif minimo <= sl:
                motivo, salida = "SL", sl
            elif maximo >= tp:
                motivo, salida = "TP", tp
        else:
            apertura = v["Open"] + SPREAD_PUNTOS
            maximo = v["High"] + SPREAD_PUNTOS
            minimo = v["Low"] + SPREAD_PUNTOS
            if apertura >= sl:
                motivo, salida = "SL (gap)", apertura
            elif maximo >= sl:
                motivo, salida = "SL", sl
            elif minimo <= tp:
                motivo, salida = "TP", tp

        if motivo:
            ts_salida = ts
            break

        # Cierre forzoso: al cierre de la vela que alcanza la hora límite
        if ts.time() >= hora_cierre:
            motivo, ts_salida = "CIERRE HORARIO", ts
            salida = v["Close"] if direccion == "LONG" else v["Close"] + SPREAD_PUNTOS
            break

    # Si se acabaron las velas del día sin cierre, cerrar en la última
    if motivo is None:
        if posteriores.empty:
            return None
        ts_salida = posteriores.index[-1]
        ultimo = posteriores.iloc[-1]["Close"]
        motivo = "CIERRE FIN DE DATOS"
        salida = ultimo if direccion == "LONG" else ultimo + SPREAD_PUNTOS

    puntos = (salida - entrada) if direccion == "LONG" else (entrada - salida)
    # Para SHORT la entrada ya es BID y la salida ya incluye el spread (ASK)
    bruto_puntos = puntos + (SPREAD_PUNTOS if direccion == "LONG" else -SPREAD_PUNTOS) * 1
    # Ganancia bruta: movimiento puro de precio, sin spread
    bruto_usd = bruto_puntos * VALOR_POR_PUNTO_POR_LOTE * lotes
    spread_usd = SPREAD_PUNTOS * VALOR_POR_PUNTO_POR_LOTE * lotes
    comision_usd = COMISION_POR_LOTE * lotes
    neto_usd = puntos * VALOR_POR_PUNTO_POR_LOTE * lotes - comision_usd

    return {
        "Entrada_TS": ts_señal,
        "Salida_TS": ts_salida,
        "Direccion": direccion,
        "Lotes": lotes,
        "Entrada": entrada,
        "Salida": salida,
        "Motivo": motivo,
        "Puntos_Netos": puntos,
        "Bruto_USD": bruto_usd,
        "Spread_USD": spread_usd,
        "Comision_USD": comision_usd,
        "Neto_USD": neto_usd,
        "Riesgo_USD": STOP_LOSS_PUNTOS * VALOR_POR_PUNTO_POR_LOTE * lotes,
    }


def calcular_metricas(trades, balance_inicial=BALANCE_INICIAL):
    """Calcula métricas globales a partir de la lista de trades simulados."""
    if not trades:
        return None
    df = pd.DataFrame(trades)
    ganadores = df[df["Neto_USD"] > 0]["Neto_USD"]
    perdedores = df[df["Neto_USD"] <= 0]["Neto_USD"]

    curva = balance_inicial + df["Neto_USD"].cumsum()
    curva_con_inicio = pd.concat([pd.Series([balance_inicial]), curva], ignore_index=True)
    pico = curva_con_inicio.cummax()
    dd_pct = ((pico - curva_con_inicio) / pico * 100).max()
    dd_usd = (pico - curva_con_inicio).max()

    suma_perdidas = abs(perdedores.sum())
    ganancia_media = ganadores.mean() if len(ganadores) else 0.0
    perdida_media = abs(perdedores.mean()) if len(perdedores) else 0.0

    return {
        "Trades": len(df),
        "Ganadores": len(ganadores),
        "Perdedores": len(perdedores),
        "Win_Rate": len(ganadores) / len(df) * 100,
        "Bruto_Total": df["Bruto_USD"].sum(),
        "Costos_Spread": df["Spread_USD"].sum(),
        "Costos_Comision": df["Comision_USD"].sum(),
        "Neto_Total": df["Neto_USD"].sum(),
        "Balance_Final": balance_inicial + df["Neto_USD"].sum(),
        "Retorno_Pct": df["Neto_USD"].sum() / balance_inicial * 100,
        "Profit_Factor": (ganadores.sum() / suma_perdidas) if suma_perdidas > 0 else float("inf"),
        "Expectancy": df["Neto_USD"].mean(),
        "Max_DD_Pct": dd_pct,
        "Max_DD_USD": dd_usd,
        "Ganancia_Media": ganancia_media,
        "Perdida_Media": perdida_media,
        "Ratio_RB": (ganancia_media / perdida_media) if perdida_media > 0 else float("inf"),
    }


def imprimir_reporte(trades, metricas, ticker=TICKER):
    """Imprime el detalle de cada trade y el resumen final."""
    print("\n" + "=" * 78)
    print(f" BACKTEST PDH/PDL | {ticker} | BALANCE INICIAL: ${BALANCE_INICIAL:.2f} | "
          f"RIESGO: {RIESGO_POR_TRADE_PCT}%")
    print(f" SL: {STOP_LOSS_PUNTOS} pts | TP: {TAKE_PROFIT_PUNTOS} pts | "
          f"Spread: {SPREAD_PUNTOS} pts | Comisión: ${COMISION_POR_LOTE}/lote")
    print("=" * 78)

    if not trades:
        print("No se registraron entradas en el periodo seleccionado.")
        return

    for i, t in enumerate(trades, 1):
        print(f"\n[#{i}] {t['Entrada_TS']:%Y-%m-%d %H:%M} -> {t['Salida_TS']:%H:%M} | "
              f"{t['Direccion']} | {t['Lotes']:.2f} lotes")
        print(f"   Entrada: {t['Entrada']:.2f} | Salida: {t['Salida']:.2f} | Motivo: {t['Motivo']}")
        print(f"   Bruto: {t['Bruto_USD']:+.2f} USD | Spread: -{t['Spread_USD']:.2f} | "
              f"Comisión: -{t['Comision_USD']:.2f} | NETO: {t['Neto_USD']:+.2f} USD")
        print(f"   Balance tras trade: ${t['Balance_Despues']:.2f}")

    m = metricas
    pf = "∞" if m["Profit_Factor"] == float("inf") else f"{m['Profit_Factor']:.2f}"
    rr = "∞" if m["Ratio_RB"] == float("inf") else f"{m['Ratio_RB']:.2f}"
    print("\n" + "=" * 78)
    print(" RESUMEN FINAL")
    print("=" * 78)
    print(f" • Trades: {m['Trades']} ({m['Ganadores']} ganadores / {m['Perdedores']} perdedores)")
    print(f" • Win Rate: {m['Win_Rate']:.1f}%")
    print(f" • Ganancia BRUTA total: {m['Bruto_Total']:+.2f} USD")
    print(f" • Costos: spread -{m['Costos_Spread']:.2f} USD | comisiones -{m['Costos_Comision']:.2f} USD")
    print(f" • Ganancia NETA total:  {m['Neto_Total']:+.2f} USD ({m['Retorno_Pct']:+.1f}%)")
    print(f" • Balance final: ${m['Balance_Final']:.2f}")
    print(f" • Profit Factor: {pf}")
    print(f" • Expectancy por trade: {m['Expectancy']:+.2f} USD")
    print(f" • Max Drawdown: {m['Max_DD_Pct']:.2f}% (${m['Max_DD_USD']:.2f})")
    print(f" • Ganancia media: +{m['Ganancia_Media']:.2f} | Pérdida media: -{m['Perdida_Media']:.2f} "
          f"| Ratio Riesgo/Beneficio real: {rr}")


def ejecutar_backtest(df):
    """Recorre los días, detecta toques y simula los trades actualizando el balance."""
    dias = sorted(df["Date"].unique())[-DIAS_ANALISIS - 1:]
    balance = BALANCE_INICIAL
    trades = []

    for i in range(1, len(dias)):
        previo = df[df["Date"] == dias[i - 1]]
        actual = df[df["Date"] == dias[i]]
        pdh, pdl = previo["High"].max(), previo["Low"].min()

        n_dia = 0
        ultima_entrada = None
        libre_desde = None  # no se solapan trades: una posición a la vez

        for ts, direccion, _tipo, precio in detectar_toques(actual, pdh, pdl):
            if n_dia >= MAX_TRADES_POR_DIA:
                break
            if libre_desde is not None and ts <= libre_desde:
                continue
            if ultima_entrada is not None and \
                    (ts - ultima_entrada) < pd.Timedelta(minutes=MINUTOS_ENTRE_ENTRADAS):
                continue

            t = simular_trade(actual, ts, direccion, precio, balance)
            if t is None:
                continue
            balance += t["Neto_USD"]
            t["Balance_Despues"] = balance
            trades.append(t)
            n_dia += 1
            ultima_entrada = ts
            libre_desde = t["Salida_TS"]

    return trades


def main():
    df = descargar_datos()
    if df is None:
        sys.exit(1)
    trades = ejecutar_backtest(df)
    metricas = calcular_metricas(trades)
    imprimir_reporte(trades, metricas)


if __name__ == "__main__":
    main()
