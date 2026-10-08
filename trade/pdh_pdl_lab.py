"""
LABORATORIO PDH/PDL - Grid search + walk-forward + robustez.

Reutiliza la lógica de pdh_pdl_mt5_explorer.py (que queda intacto) pero:
  - Todos los parámetros se pasan como argumentos (dict `params`), no hay
    constantes globales de estrategia.
  - La simulación trabaja sobre arrays numpy (rápido) en vez de iterrows.
  - Los datos se descargan UNA vez y se reutilizan en todas las combinaciones.

Uso:  python pdh_pdl_lab.py
"""
import os
import sys
import time
import itertools
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")  # solo guardamos PNG, no abrimos ventanas
import matplotlib.pyplot as plt

try:
    from tqdm import tqdm
except ImportError:  # sin tqdm: progreso simple cada 50 combinaciones
    tqdm = None

warnings.filterwarnings("ignore")

# ==============================================================================
# CONSTANTES FIJAS DEL ENTORNO (no son parámetros de la estrategia a optimizar)
# ==============================================================================
TICKER_PRINCIPAL = "NQ=F"
TICKERS_VALIDACION = ["ES=F", "YM=F"]
PERIODO = "60d"
INTERVALO = "5m"
ZONA_HORARIA = "America/New_York"

BALANCE_INICIAL = 1000.0
VALOR_POR_PUNTO_POR_LOTE = 10.0
LOTE_MINIMO = 0.01
PASO_LOTE = 0.01
SPREAD_PUNTOS = 0.5
COMISION_POR_LOTE = 3.5
TOLERANCIA_PCT = 0.001
RIESGO_POR_TRADE_PCT = 1.0
MINUTOS_ENTRE_ENTRADAS = 30

HORA_INICIO = "09:30"
HORA_CIERRE = "15:55"
HORA_FIN_SESION = "16:00"

PCT_IN_SAMPLE = 0.60
MIN_TRADES_RANKING = 15      # mínimo de trades para entrar en rankings (evita PF falsos)
MIN_TRADES_OOS = 8           # mínimo de trades OOS para considerar válida una config
PF_CAP = 999.0
CARPETA = "resultados"

# --- Matriz del grid ---
GRID_SL = [10, 15, 20, 25, 30, 40, 50]
GRID_TP = [20, 30, 40, 60, 80, 100]
GRID_MAX_TRADES = [1, 2, 3]
GRID_TRAILING = [15, 25, 35, 50]
GRID_HORAS = ["12:00", "14:00", "15:00"]


def a_minutos(hhmm):
    """'HH:MM' -> minutos desde medianoche."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# ==============================================================================
# DATOS
# ==============================================================================
def descargar_datos(ticker, periodo=PERIODO, intervalo=INTERVALO):
    """Descarga velas de yfinance y filtra la sesión regular. Devuelve None si falla."""
    print(f"Descargando {ticker} ({periodo}, {intervalo})...")
    try:
        df = yf.download(ticker, period=periodo, interval=intervalo,
                         progress=False, auto_adjust=False)
    except Exception as e:
        print(f"  ERROR descargando {ticker}: {e}")
        return None
    if df is None or df.empty:
        print(f"  ERROR: sin datos para {ticker}")
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(ZONA_HORARIA)
    df = df.between_time(HORA_INICIO, HORA_FIN_SESION, inclusive="left")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if df.empty:
        return None
    df["Date"] = df.index.date
    return df


def preparar_dias(df):
    """
    Convierte el DataFrame en una lista de días con arrays numpy y PDH/PDL
    (del día anterior). Se hace UNA vez; el primer día solo sirve de referencia.
    Cada día pre-calcula sus velas de toque (índice, dirección, cierre).
    """
    fechas = sorted(df["Date"].unique())
    dias = []
    for i in range(1, len(fechas)):
        previo = df[df["Date"] == fechas[i - 1]]
        actual = df[df["Date"] == fechas[i]]
        if len(actual) < 10 or previo.empty:
            continue
        pdh, pdl = float(previo["High"].max()), float(previo["Low"].min())
        o = actual["Open"].to_numpy(float)
        h = actual["High"].to_numpy(float)
        l = actual["Low"].to_numpy(float)
        c = actual["Close"].to_numpy(float)
        minutos = (actual.index.hour * 60 + actual.index.minute).to_numpy()
        # Toques (misma regla que el explorer): SHORT si High entra a zona PDH,
        # si no LONG si Low entra a zona PDL
        toca_pdh = h >= pdh * (1 - TOLERANCIA_PCT)
        toca_pdl = (~toca_pdh) & (l <= pdl * (1 + TOLERANCIA_PCT))
        idx_sig = np.where(toca_pdh | toca_pdl)[0]
        dias.append({
            "fecha": fechas[i], "pdh": pdh, "pdl": pdl,
            "o": o, "h": h, "l": l, "c": c, "min": minutos,
            "sig_idx": idx_sig,
            "sig_dir": np.where(toca_pdh[idx_sig], -1, 1),  # -1 SHORT, +1 LONG
        })
    return dias


# ==============================================================================
# SIMULACIÓN
# ==============================================================================
def calcular_lotes(balance, sl_puntos):
    """Lotes para arriesgar RIESGO_POR_TRADE_PCT del balance con el SL dado."""
    riesgo_usd = balance * RIESGO_POR_TRADE_PCT / 100
    lotes = riesgo_usd / (sl_puntos * VALOR_POR_PUNTO_POR_LOTE)
    lotes = np.floor(lotes / PASO_LOTE) * PASO_LOTE
    return round(max(lotes, LOTE_MINIMO), 2)


def simular_trade(dia, i_sig, direccion, balance, params):
    """
    Simula un trade vela por vela desde la vela siguiente a la señal.
    Para SHORT se suma el spread a los precios (ASK) y se razona en espejo.
    Si una vela toca SL y TP, se asume SL primero (peor caso).
    Modo TRAILING: sin TP, el stop sigue al mejor precio a distancia `trailing_puntos`
    (se evalúa con el stop de la vela anterior, luego se actualiza).
    Devuelve (idx_salida, puntos_netos, motivo, lotes, neto_usd) o None.
    """
    sl = float(params["sl_puntos"])
    tp = float(params["tp_puntos"])
    trailing = float(params["trailing_puntos"])
    modo_trail = params["modo_salida"] == "TRAILING"
    cierre_min = a_minutos(HORA_CIERRE)

    lotes = calcular_lotes(balance, sl)
    n = len(dia["c"])
    if i_sig + 1 >= n:
        return None

    precio = dia["c"][i_sig]
    if direccion == 1:   # LONG: entra al ASK
        entrada = precio + SPREAD_PUNTOS
        add = 0.0
        stop = entrada - sl
        objetivo = entrada + tp
    else:                # SHORT: entra al BID; los precios de datos se leen +spread
        entrada = precio
        add = SPREAD_PUNTOS
        stop = entrada + sl
        objetivo = entrada - tp
    mejor = entrada

    salida, motivo, j_sal = None, None, None
    for j in range(i_sig + 1, n):
        ap = dia["o"][j] + add
        mx = dia["h"][j] + add
        mn = dia["l"][j] + add
        if direccion == 1:
            if ap <= stop:
                motivo, salida = "SL (gap)", ap
            elif mn <= stop:
                motivo, salida = ("TRAIL" if modo_trail and stop > entrada - sl else "SL"), stop
            elif (not modo_trail) and mx >= objetivo:
                motivo, salida = "TP", objetivo
        else:
            if ap >= stop:
                motivo, salida = "SL (gap)", ap
            elif mx >= stop:
                motivo, salida = ("TRAIL" if modo_trail and stop < entrada + sl else "SL"), stop
            elif (not modo_trail) and mn <= objetivo:
                motivo, salida = "TP", objetivo
        if motivo:
            j_sal = j
            break
        if modo_trail:  # actualizar stop con el extremo de esta vela
            if direccion == 1:
                mejor = max(mejor, mx)
                stop = max(stop, mejor - trailing)
            else:
                mejor = min(mejor, mn)
                stop = min(stop, mejor + trailing)
        if dia["min"][j] >= cierre_min:
            motivo, j_sal = "CIERRE HORARIO", j
            salida = dia["c"][j] + add
            break

    if motivo is None:  # se acabaron las velas
        j_sal = n - 1
        motivo = "CIERRE FIN DE DATOS"
        salida = dia["c"][j_sal] + add

    puntos = (salida - entrada) if direccion == 1 else (entrada - salida)
    neto = puntos * VALOR_POR_PUNTO_POR_LOTE * lotes - COMISION_POR_LOTE * lotes
    return j_sal, puntos, motivo, lotes, neto


def ejecutar_backtest_un_dia(datos_dia, pdh, pdl, params, balance_inicial):
    """
    Corre un día con la configuración `params`. Devuelve la lista de trades (dicts).
    pdh/pdl ya vienen calculados del día anterior (se guardan en el trade).
    Reglas: una posición a la vez, mínimo MINUTOS_ENTRE_ENTRADAS entre entradas,
    máximo `max_trades_dia`, sin entradas después de `hora_ultima_entrada`.
    """
    hora_max = a_minutos(params["hora_ultima_entrada"])
    max_trades = params["max_trades_dia"]
    balance = balance_inicial
    trades = []
    ultima_entrada_min = None
    libre_desde = -1  # índice de vela hasta el cual hay posición abierta

    for i, direccion in zip(datos_dia["sig_idx"], datos_dia["sig_dir"]):
        minuto = datos_dia["min"][i]
        if minuto > hora_max or len(trades) >= max_trades:
            break
        if i <= libre_desde:
            continue
        if ultima_entrada_min is not None and minuto - ultima_entrada_min < MINUTOS_ENTRE_ENTRADAS:
            continue
        r = simular_trade(datos_dia, i, int(direccion), balance, params)
        if r is None:
            continue
        j_sal, puntos, motivo, lotes, neto = r
        balance += neto
        trades.append({
            "Fecha": datos_dia["fecha"], "Dir": "LONG" if direccion == 1 else "SHORT",
            "Entrada_Min": int(minuto), "Salida_Min": int(datos_dia["min"][j_sal]),
            "Puntos": puntos, "Lotes": lotes, "Motivo": motivo,
            "Neto_USD": neto, "PDH": pdh, "PDL": pdl,
        })
        ultima_entrada_min = minuto
        libre_desde = j_sal
        if balance <= 0:
            break
    return trades


def racha_maxima(serie_bool):
    """Longitud de la racha más larga de True consecutivos."""
    mejor = actual = 0
    for v in serie_bool:
        actual = actual + 1 if v else 0
        mejor = max(mejor, actual)
    return mejor


def calcular_metricas(trades, retornos_diarios, n_dias, balance_inicial=BALANCE_INICIAL):
    """Métricas de una corrida. Devuelve dict o None si no hay trades."""
    if not trades:
        return None
    netos = np.array([t["Neto_USD"] for t in trades])
    gan, per = netos[netos > 0], netos[netos <= 0]
    suma_per = abs(per.sum())
    pf = gan.sum() / suma_per if suma_per > 0 else PF_CAP
    pf = min(pf, PF_CAP)  # inf -> 999 para poder ordenar

    curva = np.concatenate([[balance_inicial], balance_inicial + np.cumsum(netos)])
    pico = np.maximum.accumulate(curva)
    dd_usd = (pico - curva).max()
    dd_pct = ((pico - curva) / np.where(pico > 0, pico, 1) * 100).max()

    r = np.asarray(retornos_diarios, float)
    std = r.std(ddof=1) if len(r) > 1 else 0.0
    sharpe = r.mean() / std * np.sqrt(252) if std > 0 else 0.0
    neg = np.minimum(r, 0.0)
    down = np.sqrt((neg ** 2).mean()) if len(r) else 0.0
    sortino = r.mean() / down * np.sqrt(252) if down > 0 else 0.0

    neto_total = netos.sum()
    retorno_pct = neto_total / balance_inicial * 100
    ret_anual = retorno_pct * 252 / max(n_dias, 1)
    calmar = ret_anual / dd_pct if dd_pct > 0 else 0.0

    # Consistencia: % de días ganadores sobre los días en que se operó
    pnl_dia = pd.Series(netos).groupby([t["Fecha"] for t in trades]).sum()
    consistencia = (pnl_dia > 0).mean() * 100

    return {
        "Total_Trades": len(netos),
        "Win_Rate": len(gan) / len(netos) * 100,
        "Profit_Factor": pf,
        "Expectancy": netos.mean(),
        "Neto_USD": neto_total,
        "Retorno_Pct": retorno_pct,
        "Max_DD_Pct": dd_pct,
        "Max_DD_USD": dd_usd,
        "Sharpe_Ratio": sharpe,
        "Sortino_Ratio": sortino,
        "Calmar_Ratio": calmar,
        "Consistencia_Pct": consistencia,
        "Racha_Max_Perdidas": racha_maxima(netos <= 0),
        "Racha_Max_Ganancias": racha_maxima(netos > 0),
        "Trades_por_Dia_Promedio": len(netos) / max(n_dias, 1),
    }


def backtest_completo(dias, params, balance_inicial=BALANCE_INICIAL):
    """
    Corre todos los días (lista de `preparar_dias`) con `params`.
    Devuelve (DataFrame de trades, dict de métricas o None).
    El balance se compone entre días; los retornos diarios incluyen días sin trades (0).
    """
    balance = balance_inicial
    todos, retornos = [], []
    for d in dias:
        trades = ejecutar_backtest_un_dia(d, d["pdh"], d["pdl"], params, balance)
        pnl = sum(t["Neto_USD"] for t in trades)
        retornos.append(pnl / balance if balance > 0 else 0.0)
        balance += pnl
        todos.extend(trades)
        if balance <= 0:
            break
    df_trades = pd.DataFrame(todos)
    return df_trades, calcular_metricas(todos, retornos, len(dias), balance_inicial)


# ==============================================================================
# GRID SEARCH
# ==============================================================================
def generar_combinaciones():
    """Lista de dicts de parámetros: TP_FIJO (SL x TP x trades x hora) y TRAILING (SL x trail x trades x hora)."""
    combos = []
    for sl, tp, mt, h in itertools.product(GRID_SL, GRID_TP, GRID_MAX_TRADES, GRID_HORAS):
        combos.append({"sl_puntos": sl, "tp_puntos": tp, "max_trades_dia": mt,
                       "modo_salida": "TP_FIJO", "trailing_puntos": 0, "hora_ultima_entrada": h})
    for sl, tr, mt, h in itertools.product(GRID_SL, GRID_TRAILING, GRID_MAX_TRADES, GRID_HORAS):
        combos.append({"sl_puntos": sl, "tp_puntos": 0, "max_trades_dia": mt,
                       "modo_salida": "TRAILING", "trailing_puntos": tr, "hora_ultima_entrada": h})
    return combos


def clave_config(p):
    return (p["sl_puntos"], p["tp_puntos"], p["max_trades_dia"],
            p["modo_salida"], p["trailing_puntos"], p["hora_ultima_entrada"])


def grid_search(dias, combos=None, etiqueta="grid"):
    """Evalúa cada combinación; un fallo o una config sin trades no rompe el grid."""
    combos = combos if combos is not None else generar_combinaciones()
    filas = []
    iterador = tqdm(combos, desc=etiqueta, unit="cfg") if tqdm else combos
    for k, p in enumerate(iterador, 1):
        if not tqdm and k % 50 == 0:
            print(f"  [{etiqueta}] {k}/{len(combos)} combinaciones")
        base = {"SL": p["sl_puntos"], "TP": p["tp_puntos"], "MaxTrades": p["max_trades_dia"],
                "Modo": p["modo_salida"], "Trailing": p["trailing_puntos"],
                "HoraLimite": p["hora_ultima_entrada"]}
        try:
            _, m = backtest_completo(dias, p)
            if m is None:
                base["Estado"] = "sin_datos"
            else:
                base.update(m)
                base["Estado"] = "ok"
        except Exception as e:  # un fallo no rompe todo el grid
            base["Estado"] = f"error: {e}"
        filas.append(base)
    return pd.DataFrame(filas)


def estimar_tiempo(dias, combos):
    """Mide 6 combinaciones representativas y extrapola el tiempo total (segundos)."""
    muestra = combos[:: max(len(combos) // 6, 1)][:6]
    t0 = time.time()
    for p in muestra:
        backtest_completo(dias, p)
    por_combo = (time.time() - t0) / len(muestra)
    return por_combo * len(combos)


def validos(res, min_trades=MIN_TRADES_RANKING):
    """Filtra configuraciones válidas para rankings."""
    return res[(res["Estado"] == "ok") & (res["Total_Trades"] >= min_trades)].copy()


def params_de_fila(fila):
    return {"sl_puntos": fila["SL"], "tp_puntos": fila["TP"], "max_trades_dia": int(fila["MaxTrades"]),
            "modo_salida": fila["Modo"], "trailing_puntos": fila["Trailing"],
            "hora_ultima_entrada": fila["HoraLimite"]}


def describir(fila):
    if fila["Modo"] == "TP_FIJO":
        return f"SL{fila['SL']}/TP{fila['TP']}"
    return f"SL{fila['SL']}/TRAIL{fila['Trailing']}"


COLS_TABLA = ["SL", "TP", "MaxTrades", "Modo", "Trailing", "HoraLimite", "Total_Trades",
              "Win_Rate", "Profit_Factor", "Neto_USD", "Retorno_Pct", "Max_DD_Pct", "Sharpe_Ratio"]


def imprimir_top(res, columna, titulo, n=10, ascendente=False):
    print(f"\n--- {titulo} ---")
    v = validos(res).sort_values(columna, ascending=ascendente).head(n)
    if v.empty:
        print("  (sin configuraciones válidas)")
        return v
    print(v[COLS_TABLA].round(2).to_string(index=False))
    return v


def puntaje_compuesto(res):
    """Ranking medio de 3 criterios: Profit Factor (mayor), Sharpe (mayor), Max DD (menor)."""
    r_pf = res["Profit_Factor"].rank(ascending=False)
    r_sh = res["Sharpe_Ratio"].rank(ascending=False)
    r_dd = res["Max_DD_Pct"].rank(ascending=True)
    return (r_pf + r_sh + r_dd) / 3


def tabla_robustez(res, columna, titulo):
    """Promedio de PF (acotado a 10 para no distorsionar), mediana, Sharpe y % de configs rentables."""
    v = validos(res)
    v["PF_acot"] = v["Profit_Factor"].clip(upper=10)
    g = v.groupby(columna).agg(
        Configs=("PF_acot", "size"), PF_Prom=("PF_acot", "mean"), PF_Mediana=("PF_acot", "median"),
        Sharpe_Prom=("Sharpe_Ratio", "mean"), Retorno_Prom=("Retorno_Pct", "mean"),
        MaxDD_Prom=("Max_DD_Pct", "mean"), Pct_Rentables=("Neto_USD", lambda s: (s > 0).mean() * 100))
    print(f"\n--- {titulo} ---")
    print(g.round(2).to_string())


# ==============================================================================
# GRÁFICO
# ==============================================================================
def graficar_equity(dias, top3, ruta):
    """Curva de equity (por trade) de las 3 mejores configuraciones."""
    fig, ax = plt.subplots(figsize=(11, 6))
    for k, (_, fila) in enumerate(top3.iterrows(), 1):
        tr, _ = backtest_completo(dias, params_de_fila(fila))
        if tr.empty:
            continue
        eq = np.concatenate([[BALANCE_INICIAL], BALANCE_INICIAL + tr["Neto_USD"].cumsum().to_numpy()])
        ax.plot(eq, label=f"#{k} {describir(fila)} | max{int(fila['MaxTrades'])} | "
                          f"<= {fila['HoraLimite']} | PF {fila['Profit_Factor']:.2f}")
    ax.axhline(BALANCE_INICIAL, color="gray", ls="--", lw=0.8)
    ax.set_title(f"Curva de equity - Top 3 configuraciones ({TICKER_PRINCIPAL})")
    ax.set_xlabel("Nº de trade")
    ax.set_ylabel("Balance (USD)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=120)
    plt.close(fig)


# ==============================================================================
# PROGRAMA PRINCIPAL
# ==============================================================================
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(CARPETA, exist_ok=True)

    # 1) Datos: se descargan una sola vez
    df = descargar_datos(TICKER_PRINCIPAL)
    if df is None:
        sys.exit(1)
    dias = preparar_dias(df)
    n_is = int(len(dias) * PCT_IN_SAMPLE)
    dias_is, dias_oos = dias[:n_is], dias[n_is:]
    print(f"Días simulables: {len(dias)} ({dias[0]['fecha']} -> {dias[-1]['fecha']}) | "
          f"IS: {len(dias_is)} días | OOS: {len(dias_oos)} días")

    combos = generar_combinaciones()
    est = estimar_tiempo(dias, combos)
    total_pasadas = 3  # completo + IS + OOS
    print(f"Combinaciones: {len(combos)} | tiempo estimado: ~{est * total_pasadas:.0f} s "
          f"({total_pasadas} pasadas: completo, IS, OOS)")

    # 2) Grid completo, IS y OOS (mismas combinaciones)
    res = grid_search(dias, combos, "Completo")
    res_is = grid_search(dias_is, combos, "In-sample")
    res_oos = grid_search(dias_oos, combos, "Out-of-sample")

    n_ok = (res["Estado"] == "ok").sum()
    n_sd = (res["Estado"] == "sin_datos").sum()
    n_err = res["Estado"].str.startswith("error").sum()

    # 3) Walk-forward: top 10 IS (por PF) evaluado en OOS
    top_is = validos(res_is).sort_values("Profit_Factor", ascending=False).head(10)
    claves = ["SL", "TP", "MaxTrades", "Modo", "Trailing", "HoraLimite"]
    cols_m = ["Total_Trades", "Win_Rate", "Profit_Factor", "Retorno_Pct", "Max_DD_Pct", "Sharpe_Ratio"]
    wf = top_is[claves + cols_m].merge(
        res_oos[claves + cols_m + ["Estado"]], on=claves, suffixes=("_IS", "_OOS"), how="left")
    wf["Rank_IS"] = range(1, len(wf) + 1)
    # Ranking de cada config del top-IS dentro de TODO el grid OOS (por PF)
    oos_v = validos(res_oos, MIN_TRADES_OOS).copy()
    oos_v["Rank_OOS_Grid"] = oos_v["Profit_Factor"].rank(ascending=False, method="min")
    wf = wf.merge(oos_v[claves + ["Rank_OOS_Grid"]], on=claves, how="left")

    # Correlación IS vs OOS de PF en todo el grid (¿la optimización predice algo?)
    comp = validos(res_is).merge(oos_v[claves + ["Profit_Factor"]], on=claves, suffixes=("_IS", "_OOS"))
    corr = comp["Profit_Factor_IS"].clip(upper=10).corr(comp["Profit_Factor_OOS"].clip(upper=10),
                                                         method="spearman") if len(comp) > 5 else np.nan

    # 4) Recomendación: puntaje compuesto en IS, exigiendo PF>1 en IS y OOS
    cand = validos(res_is).copy()
    cand["Puntaje"] = puntaje_compuesto(cand)
    cand = cand.merge(oos_v[claves + ["Profit_Factor", "Sharpe_Ratio", "Max_DD_Pct", "Total_Trades", "Retorno_Pct"]],
                      on=claves, suffixes=("_IS", "_OOS"))
    cand_ok = cand[(cand["Profit_Factor_IS"] > 1) & (cand["Profit_Factor_OOS"] > 1)].sort_values("Puntaje")

    # 5) Guardar TODO antes de imprimir
    res_orden = res.copy()
    res_orden.to_csv(os.path.join(CARPETA, "resultados_grid.csv"), index=False)
    v_full = validos(res).copy()
    v_full["Puntaje_Compuesto"] = puntaje_compuesto(v_full)
    top20 = v_full.sort_values("Puntaje_Compuesto").head(20)
    top20.to_csv(os.path.join(CARPETA, "top20_configuraciones.csv"), index=False)
    res_is.to_csv(os.path.join(CARPETA, "resultados_grid_IS.csv"), index=False)
    res_oos.to_csv(os.path.join(CARPETA, "resultados_grid_OOS.csv"), index=False)
    wf.to_csv(os.path.join(CARPETA, "walk_forward_top10.csv"), index=False)
    top3 = v_full.sort_values("Puntaje_Compuesto").head(3)
    graficar_equity(dias, top3, os.path.join(CARPETA, "equity_top3.png"))
    sys.stdout.flush()

    # ========================== REPORTE ==========================
    print("\n" + "=" * 90)
    print(f" LABORATORIO PDH/PDL | {TICKER_PRINCIPAL} | {len(dias)} días | {len(combos)} combinaciones")
    print(f" ok: {n_ok} | sin_datos: {n_sd} | error: {n_err} | "
          f"válidas para ranking (>= {MIN_TRADES_RANKING} trades): {len(validos(res))}")
    print("=" * 90)

    imprimir_top(res, "Profit_Factor", "a) TOP 10 por PROFIT FACTOR")
    imprimir_top(res, "Retorno_Pct", "b) TOP 10 por RETORNO NETO")
    imprimir_top(res, "Sharpe_Ratio", "c) TOP 10 por SHARPE")

    tabla_robustez(res, "SL", "d) Robustez por SL")
    tabla_robustez(res[res["Modo"] == "TP_FIJO"], "TP", "e) Robustez por TP (solo TP_FIJO)")
    tabla_robustez(res, "MaxTrades", "f) Robustez por MaxTrades")
    tabla_robustez(res, "Modo", "g) Comparativa TP_FIJO vs TRAILING")
    tabla_robustez(res, "HoraLimite", "   (extra) Robustez por hora límite")

    print("\n--- h) WALK-FORWARD: top 10 In-Sample (por PF) vs Out-of-Sample ---")
    if wf.empty:
        print("  (sin configuraciones IS válidas)")
    else:
        mostrar = wf[["Rank_IS"] + claves + ["Total_Trades_IS", "Profit_Factor_IS", "Sharpe_Ratio_IS",
                                             "Total_Trades_OOS", "Profit_Factor_OOS", "Sharpe_Ratio_OOS",
                                             "Retorno_Pct_OOS", "Rank_OOS_Grid"]]
        print(mostrar.round(2).to_string(index=False))
        t1 = wf.iloc[0]
        pf_is, pf_oos = t1["Profit_Factor_IS"], t1["Profit_Factor_OOS"]
        print(f"\n  Top 1 IS: PF IS {pf_is:.2f} -> PF OOS "
              f"{'n/d' if pd.isna(pf_oos) else f'{pf_oos:.2f}'} "
              f"(ranking OOS en el grid: {t1['Rank_OOS_Grid'] if pd.notna(t1['Rank_OOS_Grid']) else 'n/d'})")
        if pd.isna(pf_oos):
            print("  VEREDICTO: sin trades suficientes en OOS para validar el top 1.")
        elif pf_oos >= 1.0 and pf_oos >= 0.7 * pf_is:
            print("  VEREDICTO: ROBUSTO - el top 1 IS mantiene un PF > 1 en OOS sin caída fuerte.")
        elif pf_oos >= 1.0:
            print("  VEREDICTO: DEGRADACIÓN - sigue rentable en OOS pero cae >30%; posible sobreajuste parcial.")
        else:
            print("  VEREDICTO: OVERFITTING - el top 1 IS pierde dinero (PF < 1) fuera de muestra.")
        n_rent = (wf["Profit_Factor_OOS"] > 1).sum()
        print(f"  Del top 10 IS, {n_rent}/10 siguen con PF > 1 en OOS.")
        print(f"  Correlación de Spearman PF(IS) vs PF(OOS) en todo el grid: "
              f"{'n/d' if pd.isna(corr) else f'{corr:.2f}'} "
              f"(cercana a 0 o negativa = optimizar en IS no predice el futuro)")

    print("\n--- i) Gráfico de equity de las 3 mejores (compuesto PF/Sharpe/MaxDD): "
          f"{os.path.join(CARPETA, 'equity_top3.png')}")

    # ---- Validación cruzada de robustez en otros índices ----
    print("\n--- Validación en otros tickers (top 3 del compuesto, periodo completo) ---")
    otros = {}
    for tk in TICKERS_VALIDACION:
        d2 = descargar_datos(tk)
        if d2 is not None:
            otros[tk] = preparar_dias(d2)
    filas = []
    for k, (_, fila) in enumerate(top3.iterrows(), 1):
        for tk, dd in {TICKER_PRINCIPAL: dias, **otros}.items():
            try:
                _, m = backtest_completo(dd, params_de_fila(fila))
            except Exception:
                m = None
            if m:
                filas.append({"Config": f"#{k} {describir(fila)} m{int(fila['MaxTrades'])} {fila['HoraLimite']}",
                              "Ticker": tk, "Trades": m["Total_Trades"], "PF": m["Profit_Factor"],
                              "Retorno_%": m["Retorno_Pct"], "MaxDD_%": m["Max_DD_Pct"], "Sharpe": m["Sharpe_Ratio"]})
    if filas:
        print(pd.DataFrame(filas).round(2).to_string(index=False))

    # ---- Métricas extendidas del top 3 ----
    print("\n--- Métricas extendidas del top 3 ---")
    ext = ["Sortino_Ratio", "Calmar_Ratio", "Consistencia_Pct", "Racha_Max_Perdidas",
           "Racha_Max_Ganancias", "Trades_por_Dia_Promedio", "Expectancy", "Max_DD_USD"]
    t3 = top3[["SL", "TP", "MaxTrades", "Modo", "Trailing", "HoraLimite"] + ext].round(2)
    print(t3.to_string(index=False))

    # ---- Conclusión automática ----
    print("\n" + "=" * 90)
    print(" CONCLUSIÓN AUTOMÁTICA")
    print("=" * 90)
    if cand_ok.empty:
        print(" Ninguna configuración tiene PF > 1 tanto en In-Sample como en Out-of-Sample.")
        print(" No hay evidencia de ventaja estadística robusta: NO se recomienda operar esta")
        print(" estrategia con dinero real sin más datos o cambios de lógica.")
    else:
        b = cand_ok.iloc[0]
        print(" Config recomendada (mejor puntaje PF+Sharpe+MaxDD en IS, con PF>1 en IS y OOS):")
        print(f"   Modo: {b['Modo']} | SL: {b['SL']} pts | "
              f"{'TP: ' + str(b['TP']) + ' pts' if b['Modo'] == 'TP_FIJO' else 'Trailing: ' + str(b['Trailing']) + ' pts'}"
              f" | Max trades/día: {int(b['MaxTrades'])} | Hora límite: {b['HoraLimite']}")
        print(f"   IS : PF {b['Profit_Factor_IS']:.2f} | Sharpe {b['Sharpe_Ratio_IS']:.2f} | "
              f"MaxDD {b['Max_DD_Pct_IS']:.1f}% | trades {int(b['Total_Trades_IS'])}")
        print(f"   OOS: PF {b['Profit_Factor_OOS']:.2f} | Sharpe {b['Sharpe_Ratio_OOS']:.2f} | "
              f"MaxDD {b['Max_DD_Pct_OOS']:.1f}% | trades {int(b['Total_Trades_OOS'])}")
        print(" Justificación: equilibra rentabilidad (PF), retorno ajustado por riesgo (Sharpe) y")
        print(" caída máxima (MaxDD), y sobrevive a la validación fuera de muestra.")
        if b["Total_Trades_OOS"] < 30:
            print(f" ADVERTENCIA: solo {int(b['Total_Trades_OOS'])} trades en OOS; la evidencia es débil (<30).")
        if len(cand_ok) > 1:
            print("\n Siguientes candidatas:")
            print(cand_ok.iloc[1:4][["SL", "TP", "MaxTrades", "Modo", "Trailing", "HoraLimite",
                                      "Profit_Factor_IS", "Profit_Factor_OOS", "Sharpe_Ratio_OOS"]]
                  .round(2).to_string(index=False))
    print("\n NOTA: ~60 días de 5m son pocos para concluir; trate esto como exploración, no prueba.")

    print(f"\nArchivos guardados en ./{CARPETA}/: resultados_grid.csv, top20_configuraciones.csv, "
          "walk_forward_top10.csv, resultados_grid_IS.csv, resultados_grid_OOS.csv, equity_top3.png")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
