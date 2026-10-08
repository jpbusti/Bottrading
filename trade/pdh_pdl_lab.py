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


def preparar_dias(df, min_velas=10):
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
        if len(actual) < min_velas or previo.empty:
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


# ==============================================================================
# ANÁLISIS DE MOVIMIENTO REAL (sin SL/TP): distribución natural post-toque
# ==============================================================================
BLOQUES_HORARIOS = [("09:30-10:30", "09:30", "10:30"), ("10:30-12:00", "10:30", "12:00"),
                    ("12:00-14:00", "12:00", "14:00"), ("14:00-15:55", "14:00", "15:55")]
UMBRALES_MFE = [20, 40, 60, 100]
UMBRALES_MAE = [20, 40, 60]
GRID_TP_MOV = list(range(5, 155, 5))
GRID_SL_MOV = list(range(5, 105, 5))
MIN_PROB_SL = 0.05  # evita que la fórmula premie SL tan anchos que casi nunca se tocan


def analizar_movimiento_post_toque(dias):
    """
    Para cada día, PRIMER toque de PDH (SHORT) y PRIMER toque de PDL (LONG), con la
    misma tolerancia que el lab. Referencia = cierre de la vela de toque (como la entrada
    del backtest). Se mide hasta la última vela antes de HORA_CIERRE, sin SL/TP ni spread.
    Devuelve (DataFrame, lista de trayectorias [(fav_acum, adv_acum)] alineada con el DataFrame).
    """
    cierre_min = a_minutos(HORA_CIERRE)
    filas, trayectorias = [], []
    for d in dias:
        n = len(d["c"])
        for nivel, direccion in (("PDH", -1), ("PDL", 1)):
            if nivel == "PDH":
                toca = d["h"] >= d["pdh"] * (1 - TOLERANCIA_PCT)
            else:
                toca = d["l"] <= d["pdl"] * (1 + TOLERANCIA_PCT)
            idx = np.where(toca)[0]
            if len(idx) == 0:
                continue
            i = int(idx[0])
            fin = np.searchsorted(d["min"], cierre_min, side="right")  # incluye vela de cierre
            fin = min(fin, n)
            if i + 1 >= fin:
                continue
            ref = d["c"][i]
            h, l = d["h"][i + 1:fin], d["l"][i + 1:fin]
            if direccion == -1:
                fav, adv = ref - l, h - ref
            else:
                fav, adv = h - ref, ref - l
            fav_acum = np.maximum.accumulate(np.maximum(fav, 0))
            adv_acum = np.maximum.accumulate(np.maximum(adv, 0))
            j_mfe = int(np.argmax(fav))
            filas.append({
                "Fecha": d["fecha"], "Nivel": nivel, "Direccion": "SHORT" if direccion == -1 else "LONG",
                "Hora_toque": int(d["min"][i]),
                "Hora_toque_hhmm": f"{d['min'][i] // 60:02d}:{d['min'][i] % 60:02d}",
                "Precio_ref": ref, "MFE_pts": max(float(fav.max()), 0.0),
                "MAE_pts": max(float(adv.max()), 0.0),
                "Duracion_min": int(d["min"][i + 1 + j_mfe] - d["min"][i]),
            })
            trayectorias.append((fav_acum, adv_acum))
    return pd.DataFrame(filas), trayectorias


def _stats_serie(s, pcts):
    out = {"promedio": s.mean(), "mediana": s.median()}
    for p in pcts:
        out[f"p{p}"] = np.percentile(s, p)
    return out


def _reporte_direccion(df, titulo):
    print(f"\n--- {titulo} (n = {len(df)} toques) ---")
    if df.empty:
        print("  (sin toques)")
        return
    mfe, mae = df["MFE_pts"], df["MAE_pts"]
    print("  MFE (pts): promedio {promedio:.1f} | mediana {mediana:.1f} | p25 {p25:.1f} | p50 {p50:.1f} | "
          "p75 {p75:.1f} | p90 {p90:.1f} | p95 {p95:.1f} | máx {mx:.1f}".format(
              **_stats_serie(mfe, [25, 50, 75, 90, 95]), mx=mfe.max()))
    print("  MAE (pts): promedio {promedio:.1f} | mediana {mediana:.1f} | p25 {p25:.1f} | p50 {p50:.1f} | "
          "p75 {p75:.1f} | p90 {p90:.1f}".format(**_stats_serie(mae, [25, 50, 75, 90])))
    print("  Días con MFE > " + " | ".join(
        f"{u} pts: {(mfe > u).sum()} ({(mfe > u).mean() * 100:.0f}%)" for u in UMBRALES_MFE))
    print("  Días con MAE > " + " | ".join(
        f"{u} pts: {(mae > u).sum()} ({(mae > u).mean() * 100:.0f}%)" for u in UMBRALES_MAE))
    print(f"  Duración hasta MFE: mediana {df['Duracion_min'].median():.0f} min | "
          f"promedio {df['Duracion_min'].mean():.0f} min")


def _ratios(df):
    mfe, mae = df["MFE_pts"], df["MAE_pts"]
    return {
        "Ratio MFE/MAE (prom. MFE / prom. MAE)": mfe.mean() / mae.mean() if mae.mean() > 0 else np.nan,
        "Ratio MFE/MAE promedio por toque": (mfe / mae.replace(0, np.nan)).mean(),
        "% MFE > MAE (favorable)": (mfe > mae).mean() * 100,
        "% MFE > 2xMAE (muy favorable)": (mfe > 2 * mae).mean() * 100,
        "% MAE > MFE (adverso)": (mae > mfe).mean() * 100,
    }


def _curvas_tp_sl(df, trayectorias, direccion):
    """Prob(alcanzar TP) y Prob(ser sacado por SL) en función de la distancia, + sugerencia."""
    mfe = df["MFE_pts"].to_numpy()
    mae = df["MAE_pts"].to_numpy()
    p_tp = np.array([(mfe >= x).mean() for x in GRID_TP_MOV])
    p_sl = np.array([(mae >= x).mean() for x in GRID_SL_MOV])

    # Sugerencia 1 (fórmula pedida): (TP * P_TP) / (SL * P_SL), con P_SL mínima
    mejor1, v1 = None, -np.inf
    for tp, pt in zip(GRID_TP_MOV, p_tp):
        for sl, ps in zip(GRID_SL_MOV, p_sl):
            if ps < MIN_PROB_SL or pt == 0:
                continue
            v = (tp * pt) / (sl * ps)
            if v > v1:
                v1, mejor1 = v, (tp, sl, pt, ps)

    # Sugerencia 2 (con orden real de eventos): esperanza en pts por trade, TP/SL en la misma vela -> SL primero
    mejor2, v2 = None, -np.inf
    for tp in GRID_TP_MOV:
        for sl in GRID_SL_MOV:
            ganados = perdidos = 0
            for fav_a, adv_a in trayectorias:
                i_tp = np.argmax(fav_a >= tp) if fav_a[-1] >= tp else None
                i_sl = np.argmax(adv_a >= sl) if adv_a[-1] >= sl else None
                if i_sl is not None and (i_tp is None or i_sl <= i_tp):
                    perdidos += 1
                elif i_tp is not None:
                    ganados += 1
            n = len(trayectorias)
            ev = (ganados * tp - perdidos * sl + (n - ganados - perdidos) * 0) / n  # sin resolver ~ 0 (aprox.)
            if ev > v2:
                v2, mejor2 = ev, (tp, sl, ganados / n, perdidos / n)
    return p_tp, p_sl, mejor1, v1, mejor2, v2


def analisis_movimiento_real(dias, carpeta=CARPETA):
    """Reporte completo + CSV + PNG del movimiento crudo post-toque de PDH/PDL."""
    os.makedirs(carpeta, exist_ok=True)
    df, trayectorias = analizar_movimiento_post_toque(dias)
    if df.empty:
        print("Sin toques de PDH/PDL en los datos.")
        return df
    df.to_csv(os.path.join(carpeta, "analisis_movimiento.csv"), index=False)

    print("\n" + "=" * 90)
    print(f" ANÁLISIS DE MOVIMIENTO REAL POST-TOQUE | {TICKER_PRINCIPAL} | {len(dias)} días | "
          f"{len(df)} toques (primer toque de cada nivel por día)")
    print(" Referencia: cierre de la vela de toque. Sin SL/TP, sin spread. Horizonte: hasta "
          f"{HORA_CIERRE}.")
    print("=" * 90)

    sh = df[df["Direccion"] == "SHORT"]
    lo = df[df["Direccion"] == "LONG"]
    _reporte_direccion(sh, "a) SHORT en PDH")
    _reporte_direccion(lo, "b) LONG en PDL")

    print("\n--- c) Tabla comparativa SHORT vs LONG ---")
    filas = []
    for nombre, g in (("SHORT (PDH)", sh), ("LONG (PDL)", lo)):
        if g.empty:
            continue
        filas.append({"Dir": nombre, "N": len(g), "MFE_prom": g["MFE_pts"].mean(),
                      "MFE_med": g["MFE_pts"].median(), "MFE_p90": g["MFE_pts"].quantile(0.9),
                      "MAE_prom": g["MAE_pts"].mean(), "MAE_med": g["MAE_pts"].median(),
                      "MAE_p90": g["MAE_pts"].quantile(0.9), "Dur_med_min": g["Duracion_min"].median(),
                      "%MFE>40": (g["MFE_pts"] > 40).mean() * 100, "%MAE>40": (g["MAE_pts"] > 40).mean() * 100})
    print(pd.DataFrame(filas).round(1).to_string(index=False))

    print("\n--- 3) Análisis de ratio MFE/MAE ---")
    tabla = pd.DataFrame({n: _ratios(g) for n, g in (("SHORT (PDH)", sh), ("LONG (PDL)", lo)) if not g.empty})
    print(tabla.round(2).to_string())

    # --- 4) Histogramas ---
    fig, axs = plt.subplots(1, 2, figsize=(13, 5))
    maximo = max(df["MFE_pts"].max(), df["MAE_pts"].max())
    bins = np.linspace(0, maximo, 30)
    for ax, col, tit in ((axs[0], "MFE_pts", "MFE (a favor)"), (axs[1], "MAE_pts", "MAE (en contra)")):
        ax.hist(sh[col], bins=bins, alpha=0.55, color="tab:red", label=f"SHORT PDH (n={len(sh)})")
        ax.hist(lo[col], bins=bins, alpha=0.55, color="tab:green", label=f"LONG PDL (n={len(lo)})")
        ax.set_title(f"{tit} - {TICKER_PRINCIPAL}")
        ax.set_xlabel("Puntos")
        ax.set_ylabel("Nº de toques")
        ax.legend()
        ax.grid(alpha=0.3)
    fig.tight_layout()
    ruta_hist = os.path.join(carpeta, "distribucion_movimiento.png")
    fig.savefig(ruta_hist, dpi=120)
    plt.close(fig)

    # --- 5) Curvas TP / SL y sugerencia ---
    print("\n--- 5) TP / SL óptimos según datos ---")
    fig, axs = plt.subplots(1, 2, figsize=(13, 5))
    for nombre, g, color in (("SHORT (PDH)", sh, "tab:red"), ("LONG (PDL)", lo, "tab:green")):
        if len(g) < 3:
            continue
        idx = [k for k, d in enumerate(df["Direccion"]) if d == g["Direccion"].iloc[0]]
        tray = [trayectorias[k] for k in idx]
        p_tp, p_sl, m1, v1, m2, v2 = _curvas_tp_sl(g, tray, nombre)
        axs[0].plot(GRID_TP_MOV, p_tp * 100, color=color, label=nombre)
        axs[1].plot(GRID_SL_MOV, p_sl * 100, color=color, label=nombre)
        print(f"  {nombre}:")
        if m1:
            print(f"    Fórmula (TP·P_TP)/(SL·P_SL), P_SL >= {MIN_PROB_SL:.0%}: TP {m1[0]} / SL {m1[1]} "
                  f"(P_TP {m1[2] * 100:.0f}%, P_SL {m1[3] * 100:.0f}%, score {v1:.2f})")
        if m2:
            print(f"    Esperanza real por orden de eventos (pts/trade, no resueltos = 0): "
                  f"TP {m2[0]} / SL {m2[1]} (TP primero {m2[2] * 100:.0f}%, SL primero {m2[3] * 100:.0f}%, "
                  f"EV {v2:+.1f} pts)")
    for ax, tit, xl in ((axs[0], "¿Qué % de toques alcanza el TP?", "TP (pts)"),
                        (axs[1], "¿Qué % de toques es sacado por el SL?", "SL (pts)")):
        ax.set_title(tit)
        ax.set_xlabel(xl)
        ax.set_ylabel("% de toques")
        ax.legend()
        ax.grid(alpha=0.3)
    fig.tight_layout()
    ruta_curvas = os.path.join(carpeta, "curvas_tp_sl.png")
    fig.savefig(ruta_curvas, dpi=120)
    plt.close(fig)

    # --- 6) Por bloque horario ---
    print("\n--- 6) Movimiento por bloque horario del toque ---")
    filas = []
    for dir_n, g in (("SHORT", sh), ("LONG", lo)):
        for nom, a, b in BLOQUES_HORARIOS:
            s = g[(g["Hora_toque"] >= a_minutos(a)) & (g["Hora_toque"] < a_minutos(b))]
            if s.empty:
                continue
            filas.append({"Dir": dir_n, "Bloque": nom, "N": len(s), "MFE_prom": s["MFE_pts"].mean(),
                          "MFE_med": s["MFE_pts"].median(), "MAE_prom": s["MAE_pts"].mean(),
                          "MAE_med": s["MAE_pts"].median(),
                          "MFE/MAE": s["MFE_pts"].mean() / s["MAE_pts"].mean() if s["MAE_pts"].mean() > 0 else np.nan,
                          "%MFE>MAE": (s["MFE_pts"] > s["MAE_pts"]).mean() * 100})
    print(pd.DataFrame(filas).round(1).to_string(index=False))
    print("  (bloques con pocos toques no son concluyentes)")

    # --- Veredicto sobre la intuición ---
    print("\n--- Veredicto: ¿el precio suele moverse a favor tras tocar el nivel? ---")
    for nombre, g in (("SHORT en PDH", sh), ("LONG en PDL", lo)):
        if g.empty:
            continue
        r = _ratios(g)
        fav = r["% MFE > MAE (favorable)"]
        print(f"  {nombre}: MFE prom {g['MFE_pts'].mean():.0f} vs MAE prom {g['MAE_pts'].mean():.0f} pts | "
              f"MFE>MAE en {fav:.0f}% de los toques -> "
              f"{'ligera ventaja a favor' if fav > 55 else 'sin ventaja clara (≈ moneda al aire)' if fav >= 45 else 'sesgo en contra'}")
    print("  Nota: MFE y MAE son máximos del día; ambos crecen con el tiempo, por lo que MFE>MAE")
    print("  no implica rentabilidad por sí solo. n pequeño (~60 días): exploración, no prueba.")

    print(f"\nArchivos: {os.path.join(carpeta, 'analisis_movimiento.csv')}, {ruta_hist}, {ruta_curvas}")
    sys.stdout.flush()
    return df


# ==============================================================================
# TEST DE FILTROS DE CONTEXTO (SL40/TP40/1 trade) en varias temporalidades
# ==============================================================================
PARAMS_BASE_FILTROS = {"sl_puntos": 40, "tp_puntos": 40, "max_trades_dia": 1,
                       "modo_salida": "TP_FIJO", "trailing_puntos": 0, "hora_ultima_entrada": "15:00"}
MINUTOS_TOQUE_TEMPRANO = 30     # filtro contexto A: el toque ocurre en los primeros 30 min
PCT_APERTURA_CERCA = 0.003      # filtro contexto B: la apertura está a <= 0.3% del nivel tocado
# (temporalidad, periodo): yfinance solo da 60d para 5m/15m/30m; 1h llega a 730d
TEMPORALIDADES = [("5m", "60d"), ("15m", "60d"), ("30m", "60d"), ("1h", "730d")]
FILTROS_CONTEXTO = ["sin_filtro", "toque_30min", "abre_cerca"]
FILTROS_RANGO = ["sin_filtro", "tendencial", "rango"]


def filtrar_dia(d, ctx, rng, umbral_rango):
    """Copia del día con las señales que cumplen los filtros (el día se mantiene, quizá sin señales)."""
    ok_rango = (rng == "sin_filtro" or
                (rng == "tendencial" and d["pdh"] - d["pdl"] >= umbral_rango) or
                (rng == "rango" and d["pdh"] - d["pdl"] < umbral_rango))
    idx, dirs = d["sig_idx"], d["sig_dir"]
    if not ok_rango or len(idx) == 0:
        mask = np.zeros(len(idx), bool)
    elif ctx == "toque_30min":
        mask = d["min"][idx] < a_minutos(HORA_INICIO) + MINUTOS_TOQUE_TEMPRANO
    elif ctx == "abre_cerca":
        nivel = np.where(dirs == -1, d["pdh"], d["pdl"])
        mask = np.abs(d["o"][0] - nivel) <= nivel * PCT_APERTURA_CERCA
    else:
        mask = np.ones(len(idx), bool)
    return {**d, "sig_idx": idx[mask], "sig_dir": dirs[mask]}


def test_filtros_contexto():
    """PF IS/OOS de la config base para cada combinación de filtros y temporalidad."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(CARPETA, exist_ok=True)
    filas = []
    for intervalo, periodo in TEMPORALIDADES:
        df = descargar_datos(TICKER_PRINCIPAL, periodo, intervalo)
        if df is None:
            continue
        dias = preparar_dias(df, min_velas=5 if intervalo == "1h" else 10)
        if not dias:
            continue
        n_is = int(len(dias) * PCT_IN_SAMPLE)
        sets = {"IS": dias[:n_is], "OOS": dias[n_is:]}
        # Umbral tendencial/rango = mediana del rango del día previo, calculada SOLO en IS (sin look-ahead)
        umbral = float(np.median([d["pdh"] - d["pdl"] for d in sets["IS"]]))
        print(f"  {intervalo}: {len(dias)} días ({dias[0]['fecha']} -> {dias[-1]['fecha']}), "
              f"IS {n_is} / OOS {len(dias) - n_is} | umbral rango (mediana IS) = {umbral:.0f} pts")
        for ctx in FILTROS_CONTEXTO:
            for rng in FILTROS_RANGO:
                fila = {"TF": intervalo, "Contexto": ctx, "Rango": rng}
                for nombre, ds in sets.items():
                    df_f = [filtrar_dia(d, ctx, rng, umbral) for d in ds]
                    tr, m = backtest_completo(df_f, PARAMS_BASE_FILTROS)
                    fila[f"Trades_{nombre}"] = m["Total_Trades"] if m else 0
                    fila[f"WR_{nombre}"] = m["Win_Rate"] if m else np.nan
                    fila[f"PF_{nombre}"] = m["Profit_Factor"] if m else np.nan
                    fila[f"Neto_{nombre}"] = m["Neto_USD"] if m else 0.0
                filas.append(fila)
    res = pd.DataFrame(filas)
    res.to_csv(os.path.join(CARPETA, "test_filtros_contexto.csv"), index=False)

    print("\n" + "=" * 100)
    print(" TEST DE FILTROS | SL40/TP40/1 trade/día, hora límite 15:00 | PF = Profit Factor (999 = sin pérdidas)")
    print(f" Contexto: toque_30min = toque en primeros {MINUTOS_TOQUE_TEMPRANO} min | "
          f"abre_cerca = apertura a <= {PCT_APERTURA_CERCA:.1%} del nivel")
    print(" Rango: tendencial = rango previo (PDH-PDL) >= mediana IS | rango = < mediana IS")
    print("=" * 100)
    cols = ["Contexto", "Rango", "Trades_IS", "WR_IS", "PF_IS", "Neto_IS",
            "Trades_OOS", "WR_OOS", "PF_OOS", "Neto_OOS"]
    for tf in res["TF"].unique():
        print(f"\n--- Temporalidad {tf} ---")
        print(res[res["TF"] == tf][cols].round(2).to_string(index=False))

    # Combinaciones con evidencia mínima: PF>1 en ambos tramos y trades suficientes
    ok = res[(res["PF_IS"] > 1) & (res["PF_OOS"] > 1) &
             (res["Trades_IS"] >= MIN_TRADES_RANKING) & (res["Trades_OOS"] >= MIN_TRADES_OOS)]
    print("\n--- Combinaciones con PF>1 en IS y OOS (>= "
          f"{MIN_TRADES_RANKING} trades IS y >= {MIN_TRADES_OOS} OOS) ---")
    print(ok[["TF"] + cols].round(2).to_string(index=False) if not ok.empty else "  (ninguna)")
    print(f"\n  {len(res)} combinaciones probadas: con tantas pruebas y pocos trades, alguna saldrá PF>1 por azar.")
    print(f"Archivo: {os.path.join(CARPETA, 'test_filtros_contexto.csv')}")
    sys.stdout.flush()


# ==============================================================================
# ANÁLISIS DE RÉGIMEN (datos 1d largos): ¿cuándo funcionó / dejó de funcionar el edge?
# ==============================================================================
CARPETA_DATOS = "data"
INICIO_1D = "2015-01-01"
VARIANTES_REG = [(40, 40), (60, 60), (40, 80), (20, 40)]   # (SL, TP) en puntos; la primera es la base
COSTO_PTS = SPREAD_PUNTOS + COMISION_POR_LOTE / VALOR_POR_PUNTO_POR_LOTE   # spread + comisión en puntos (0.85)
MIN_N_SIGNIF = 20      # menos de 20 trades: PF no significativo
MIN_N_SUFICIENTE = 30  # menos de 30: muestra insuficiente
ATR_PERIODO = 14
RET_TENDENCIA_DIAS = 20
UMBRAL_TENDENCIA = 0.03
VENTANA_MESES = 6


def _cache_csv(ruta, descargar, tz=None):
    """Reutiliza data/<archivo>.csv si tiene < 24 h; si no, descarga y guarda."""
    os.makedirs(CARPETA_DATOS, exist_ok=True)
    if os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < 86400:
        df = pd.read_csv(ruta, index_col=0)
        df.index = pd.to_datetime(df.index, utc=tz is not None)
        if tz:
            df.index = df.index.tz_convert(tz)
        print(f"  (cache) {ruta}: {len(df)} filas")
        return df
    df = descargar()
    if df is not None:
        df.drop(columns=["Date"], errors="ignore").to_csv(ruta)
        print(f"  guardado {ruta}: {len(df)} filas")
    return df


def _descargar_1d():
    print(f"Descargando {TICKER_PRINCIPAL} (1d desde {INICIO_1D})...")
    df = yf.download(TICKER_PRINCIPAL, start=INICIO_1D, interval="1d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def _sim_corto(o, h, l, c, nivel, sl, tp, pesimista):
    """
    SHORT al tocar `nivel` dentro de una vela diaria OHLC (el LONG se simula espejando precios).
    Orden intradía desconocido -> heurística estándar: el extremo más cercano a la apertura va primero.
    pesimista=True: la parte adversa (máximo) siempre va antes que la favorable (SL antes que TP).
    Devuelve puntos brutos.
    """
    entrada = max(o, nivel)
    alto_primero = pesimista or (h - o) <= (o - l)
    puntos = [h, l, c] if alto_primero else [h, c]   # si el mínimo fue antes, ya no cuenta tras la entrada
    stop, objetivo, actual = entrada + sl, entrada - tp, entrada
    for p in puntos:
        if p >= actual:
            if p >= stop:
                return -sl
        elif p <= objetivo:
            return tp
        actual = p
    return entrada - c


def simular_1d(d1, sl, tp, escalar=False, pesimista=False):
    """
    Backtest en velas diarias. PDH/PDL = máx/mín de la vela anterior; 1 trade/día; el toque se opera
    en el nivel (limit) con la tolerancia del lab. La hora límite no aplica (no hay intradía).
    escalar=True: SL/TP/costos se expresan en 'puntos de hoy' (se escalan por precio/precio_final)
    para que 40 pts valgan lo mismo en 2015 (NQ~4.400) que hoy (NQ~25.000).
    Devuelve DataFrame con Fecha, Dir, Pts (netos de costos).
    """
    o, h, l, c = (d1[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    ref = c[-1]
    filas = []
    for i in range(1, len(d1)):
        pdh, pdl = h[i - 1], l[i - 1]
        k = c[i - 1] / ref if escalar else 1.0
        niv_s, niv_l = pdh * (1 - TOLERANCIA_PCT), pdl * (1 + TOLERANCIA_PCT)
        toca_s, toca_l = h[i] >= niv_s, l[i] <= niv_l
        if not (toca_s or toca_l):
            continue
        corto = toca_s and (not toca_l or (h[i] - o[i]) <= (o[i] - l[i]))
        if corto:
            bruto = _sim_corto(o[i], h[i], l[i], c[i], niv_s, sl * k, tp * k, pesimista)
        else:   # espejo: precios negados
            bruto = _sim_corto(-o[i], -l[i], -h[i], -c[i], -niv_l, sl * k, tp * k, pesimista)
        filas.append((d1.index[i], "SHORT" if corto else "LONG", bruto / k - COSTO_PTS))
    return pd.DataFrame(filas, columns=["Fecha", "Dir", "Pts"])


def metricas_pts(pts):
    """Métricas en puntos (tamaño fijo, sin composición: comparables entre años)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    if n == 0:
        return {"N": 0, "WR": np.nan, "PF": np.nan, "Neto_pts": 0.0, "MaxDD_pts": 0.0}
    gan, per = pts[pts > 0].sum(), -pts[pts <= 0].sum()
    curva = np.cumsum(pts)
    dd = (np.maximum.accumulate(np.concatenate([[0], curva]))[1:] - curva).max()
    return {"N": n, "WR": (pts > 0).mean() * 100, "PF": min(gan / per, PF_CAP) if per > 0 else PF_CAP,
            "Neto_pts": pts.sum(), "MaxDD_pts": dd}


def nota_n(n):
    return "n<20 NO signif." if n < MIN_N_SIGNIF else ("n<30 insuf." if n < MIN_N_SUFICIENTE else "")


def _cortar(tr, ini, fin):
    """Trades con ini <= Fecha < fin (fin exclusivo)."""
    return tr[(tr["Fecha"] >= pd.Timestamp(ini)) & (tr["Fecha"] < pd.Timestamp(fin))]


def _rachas(bools):
    """Lista de (i0, i1) de las rachas de True consecutivos."""
    out, i0 = [], None
    for i, b in enumerate(bools):
        if b and i0 is None:
            i0 = i
        elif not b and i0 is not None:
            out.append((i0, i - 1))
            i0 = None
    if i0 is not None:
        out.append((i0, len(bools) - 1))
    return out


def preparar_regimenes_1d(d1):
    """Por fecha de operación: ATR14%(cierre previo), retorno 20d (cierre previo) y su régimen."""
    c = d1["Close"].astype(float)
    tr = pd.concat([d1["High"] - d1["Low"], (d1["High"] - c.shift()).abs(), (d1["Low"] - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr_pct = (tr.rolling(ATR_PERIODO).mean() / c).shift(1)                 # conocido antes de operar
    ret = (c / c.shift(RET_TENDENCIA_DIAS) - 1).shift(1)
    p33, p66 = atr_pct.quantile([1 / 3, 2 / 3])
    r = pd.DataFrame({"ATR_pct": atr_pct * 100, "Ret20": ret * 100})
    r["Vol"] = np.where(atr_pct < p33, "baja", np.where(atr_pct > p66, "alta", "media"))
    r["Vol"] = r["Vol"].where(atr_pct.notna())
    r["Tend"] = np.where(ret > UMBRAL_TENDENCIA, "alcista", np.where(ret < -UMBRAL_TENDENCIA, "bajista", "lateral"))
    r["Tend"] = r["Tend"].where(ret.notna())
    return r, p33 * 100, p66 * 100


def _tabla_periodos(tr, inicios, paso_meses, d1, extra=None):
    filas = []
    for ini in inicios:
        fin = ini + pd.DateOffset(months=paso_meses)
        sub = _cortar(tr, ini, fin)
        m = metricas_pts(sub["Pts"])
        filas.append({"Inicio": ini.date(), "Fin": (fin - pd.Timedelta(days=1)).date(), **m, "Nota": nota_n(m["N"])})
    return pd.DataFrame(filas)


def _pf_ventana(tr, ini, fin):
    return metricas_pts(_cortar(tr, ini, fin)["Pts"])


def _trades_motor(dias, params):
    """Trades del motor intradía con columnas Fecha (Timestamp) y Pts (netos de comisión)."""
    t, _ = backtest_completo(dias, params)
    if t.empty:
        return pd.DataFrame(columns=["Fecha", "Dir", "Pts"])
    return pd.DataFrame({"Fecha": pd.to_datetime(t["Fecha"]), "Dir": t["Dir"],
                         "Pts": t["Puntos"] - COMISION_POR_LOTE / VALOR_POR_PUNTO_POR_LOTE})


def _params_var(v):
    return {"sl_puntos": v[0], "tp_puntos": v[1], "max_trades_dia": 1, "modo_salida": "TP_FIJO",
            "trailing_puntos": 0, "hora_ultima_entrada": "15:00"}


def analisis_regimen(fuente="1d"):
    """
    fuente='1d': simulación sobre velas diarias (spec original; ver calibración, puede NO ser válida).
    fuente='1h': motor intradía real sobre las velas de 1h (730 días).
    """
    es_1d = fuente == "1d"
    sfx = "" if es_1d else "_1h"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(CARPETA, exist_ok=True)
    comparaciones = 0

    # ---- 1) Datos largos ----
    d1 = _cache_csv(os.path.join(CARPETA_DATOS, "NQ_1d.csv"), _descargar_1d)
    if d1 is None:
        sys.exit("Sin datos 1d")
    d1 = d1.dropna(subset=["Open", "High", "Low", "Close"])
    df1h = _cache_csv(os.path.join(CARPETA_DATOS, "NQ_1h.csv"),
                      lambda: descargar_datos(TICKER_PRINCIPAL, "730d", "1h"), tz=ZONA_HORARIA)
    if df1h is not None:
        df1h["Date"] = df1h.index.date
    ultimo = d1.index[-1]
    print(f"\n1d: {len(d1)} velas ({d1.index[0].date()} -> {ultimo.date()}) | "
          f"1h: {0 if df1h is None else len(df1h)} velas")

    # ---- Simulación (una vez por variante; tamaño fijo => se puede cortar por fechas) ----
    base = VARIANTES_REG[0]
    sim1d = {v: simular_1d(d1, *v) for v in VARIANTES_REG}
    sim1d_p = {v: simular_1d(d1, *v, pesimista=True) for v in VARIANTES_REG}
    dias1h = preparar_dias(df1h, min_velas=5) if df1h is not None else []
    t1h_var = {v: _trades_motor(dias1h, _params_var(v)) for v in VARIANTES_REG} if dias1h else {}
    t1h = t1h_var.get(base)
    if es_1d:
        trades = sim1d
        trades_n = {v: simular_1d(d1, *v, escalar=True) for v in VARIANTES_REG}
        trades_p = sim1d_p
    else:
        if not dias1h:
            sys.exit("Sin datos 1h")
        trades = trades_n = trades_p = t1h_var   # 1h: sin variantes escalada/pesimista
    tb, tbn, tbp = trades[base], trades_n[base], trades_p[base]
    reg, p33, p66 = preparar_regimenes_1d(d1)
    tb = tb.join(reg, on="Fecha")
    tbn = tbn.join(reg, on="Fecha")
    print(f"\n######## FUENTE DE TRADES: {'SIMULACIÓN SOBRE VELAS DIARIAS (1d)' if es_1d else 'MOTOR INTRADÍA SOBRE VELAS 1h'} ########")

    # ---- Calibración de la simulación diaria contra el motor intradía (5m, 48 días) ----
    print("\n" + "=" * 100)
    print(" ADVERTENCIA METODOLÓGICA: una vela diaria no dice qué ocurrió primero (SL o TP). Con rangos diarios")
    print(" de ~200-300 pts y SL/TP de 40 pts, casi siempre se alcanzan ambos: el resultado depende del orden")
    print(" supuesto. Por eso se calibra contra el motor intradía y se reporta también el caso pesimista.")
    print("=" * 100)
    d5 = descargar_datos(TICKER_PRINCIPAL, PERIODO, "5m")
    calib_ok = None   # None = no se pudo calibrar
    if d5 is not None:
        dias5 = preparar_dias(d5)
        p5 = {"sl_puntos": base[0], "tp_puntos": base[1], "max_trades_dia": 1, "modo_salida": "TP_FIJO",
              "trailing_puntos": 0, "hora_ultima_entrada": "15:00"}
        t5 = _trades_motor(dias5, p5)
        ini5, fin5 = pd.Timestamp(dias5[0]["fecha"]), pd.Timestamp(dias5[-1]["fecha"]) + pd.Timedelta(days=1)
        ref = metricas_pts(t5["Pts"])
        filas = [("Motor 5m (referencia)", ref)]
        cand = {"Sim. 1d heurística": sim1d[base], "Sim. 1d pesimista": sim1d_p[base]}
        if t1h is not None:
            cand["Motor 1h"] = t1h
        for nom, t in cand.items():
            filas.append((nom, metricas_pts(_cortar(t, ini5, fin5)["Pts"])))
        print(f"\n--- Calibración SL{base[0]}/TP{base[1]} en los mismos {len(dias5)} días ({dias5[0]['fecha']} -> "
              f"{dias5[-1]['fecha']}) ---")
        print(pd.DataFrame([{"Método": n, **m} for n, m in filas]).round(2).to_string(index=False))
        fuente_cal = filas[1][1] if es_1d else filas[-1][1]
        calib_ok = (abs(fuente_cal["PF"] - ref["PF"]) <= 0.3 * ref["PF"] and abs(fuente_cal["WR"] - ref["WR"]) <= 10)
        print(f" Criterio: PF dentro de ±30% y WR dentro de ±10 pts del motor 5m -> fuente '{fuente}': "
              f"{'CALIBRACIÓN OK' if calib_ok else 'CALIBRACIÓN FALLA (resultados NO fiables)'}")

    # ---- 2) Análisis por año ----
    años = list(range(d1.index[0].year, ultimo.year + 1))
    ATR_anual = {}
    filas = []
    for a in años:
        ini, fin = pd.Timestamp(a, 1, 1), pd.Timestamp(a + 1, 1, 1)
        px = d1[(d1.index >= ini) & (d1.index < fin)]
        prev = d1[d1.index < ini]["Close"]
        c0 = prev.iloc[-1] if len(prev) else px["Close"].iloc[0]
        ret = (px["Close"].iloc[-1] / c0 - 1) * 100
        atr = reg.loc[(reg.index >= ini) & (reg.index < fin), "ATR_pct"].mean()
        ATR_anual[a] = atr
        m = _pf_ventana(tb, ini, fin)
        mn = _pf_ventana(tbn, ini, fin)
        mp = _pf_ventana(tbp, ini, fin)
        fila = {"Año": f"{a}{'*' if a == ultimo.year else ''}", "N": m["N"], "WR": m["WR"], "PF": m["PF"],
                "Neto_pts": m["Neto_pts"], "MaxDD_pts": m["MaxDD_pts"], "Ret_%": ret, "ATR_%": atr,
                "PF_escalado": mn["PF"], "PF_pesim": mp["PF"], "Nota": nota_n(m["N"])}
        for v in VARIANTES_REG[1:]:
            fila[f"PF_{v[0]}/{v[1]}"] = _pf_ventana(trades[v], ini, fin)["PF"]
        filas.append(fila)
    anual = pd.DataFrame(filas)
    anual = anual[anual["N"] > 0].reset_index(drop=True)
    med_atr = np.median(list(ATR_anual.values()))
    anual["Tendencia"] = np.where(anual["Ret_%"] > 10, "alcista", np.where(anual["Ret_%"] < -10, "bajista", "lateral"))
    anual["Volatilidad"] = np.where(anual["ATR_%"] > med_atr * 1.15, "alta", np.where(anual["ATR_%"] < med_atr * 0.85, "baja", "normal"))
    anual.to_csv(os.path.join(CARPETA, f"resultados_regimen_anual{sfx}.csv"), index=False)
    comparaciones += len(anual) * (3 + len(VARIANTES_REG) - 1)
    print("\n" + "=" * 100)
    print(f" 1) TABLA AÑO POR AÑO | NQ=F 1d | SL{base[0]}/TP{base[1]}, 1 trade/día | puntos netos de costos ({COSTO_PTS} pts)")
    print(" PF = puntos fijos | PF_escalado = SL/TP equivalentes a precio de hoy | PF_pesim = SL antes que TP")
    print(" Tendencia: retorno anual >+10% alcista, <-10% bajista | Vol: ATR% vs mediana de años | * = año parcial")
    print("=" * 100)
    cols = ["Año", "N", "WR", "PF", "Neto_pts", "MaxDD_pts", "Ret_%", "ATR_%", "Tendencia", "Volatilidad",
            "PF_escalado", "PF_pesim"][: 10 if es_1d is False else 12] + \
           [f"PF_{v[0]}/{v[1]}" for v in VARIANTES_REG[1:]] + ["Nota"]
    print(anual[cols].round(2).to_string(index=False))
    pf_a = anual["PF"].where(anual["N"] >= MIN_N_SIGNIF)
    print(f"\n  Años con PF>1: {(pf_a > 1).sum()}/{pf_a.notna().sum()} | "
          f"PF mediano {pf_a.median():.2f} | PF_escalado mediano {anual['PF_escalado'].median():.2f}")

    # ---- 3) Semestres y trimestres ----
    ini_s = pd.date_range(pd.Timestamp(años[0], 1, 1), ultimo, freq="6MS")
    sem = _tabla_periodos(tb, ini_s, 6, d1)
    sem.insert(0, "Periodo", [f"{i.year}-H{1 if i.month <= 6 else 2}" for i in ini_s])
    sem.to_csv(os.path.join(CARPETA, f"resultados_regimen_semestral{sfx}.csv"), index=False)
    ini_q = pd.date_range(pd.Timestamp(años[0], 1, 1), ultimo, freq="QS")
    tri = _tabla_periodos(tb, ini_q, 3, d1)
    tri.insert(0, "Periodo", [f"{i.year}-Q{(i.month - 1) // 3 + 1}" for i in ini_q])
    comparaciones += len(sem) + len(tri)
    corte = ultimo - pd.DateOffset(years=3)
    print("\n" + "=" * 100)
    print(" 2) TABLA SEMESTRE POR SEMESTRE (últimos 3 años)")
    print("=" * 100)
    print(sem[pd.to_datetime(sem["Inicio"]) >= corte][["Periodo", "N", "WR", "PF", "Neto_pts", "MaxDD_pts", "Nota"]]
          .round(2).to_string(index=False))
    for nombre, t in (("semestre", sem), ("trimestre", tri)):
        v = t[(t["N"] >= MIN_N_SIGNIF) & (t["PF"] > 1)]
        print(f"  Último {nombre} con PF>1 (n>=20): {v['Periodo'].iloc[-1] if len(v) else 'ninguno'} "
              f"(PF {v['PF'].iloc[-1]:.2f})" if len(v) else f"  Último {nombre} con PF>1 (n>=20): ninguno")
    s_ok = sem[sem["N"] >= MIN_N_SIGNIF].reset_index(drop=True)
    if len(s_ok) > 4:
        y = s_ok["PF"].clip(upper=5)
        rho = pd.Series(range(len(y))).corr(y, method="spearman")
        pend = np.polyfit(range(len(y)), y, 1)[0] * 2   # cambio de PF por año
        try:
            from scipy.stats import spearmanr
            pval = spearmanr(range(len(y)), y)[1]
        except Exception:
            pval = np.nan
        print(f"  Tendencia del PF semestral (n={len(y)}): pendiente {pend:+.3f} PF/año | Spearman {rho:+.2f}"
              f"{'' if np.isnan(pval) else f' (p={pval:.2f})'} -> "
              f"{'sin tendencia significativa (compatible con ruido)' if np.isnan(pval) or pval > 0.05 else 'tendencia ' + ('creciente' if rho > 0 else 'DECRECIENTE')}")

    # ---- 4) Ventanas rodantes ----
    primero = d1.index[0] if es_1d else tb["Fecha"].min()
    inicios = pd.date_range(primero.to_period("M").to_timestamp(), ultimo, freq="MS")
    filas = []
    for ini in inicios:
        fin = ini + pd.DateOffset(months=VENTANA_MESES)
        if fin > ultimo + pd.Timedelta(days=1):
            break
        m = _pf_ventana(tb, ini, fin)
        filas.append({"Inicio": ini.date(), "Fin": (fin - pd.Timedelta(days=1)).date(), **m})
    roll = pd.DataFrame(filas)
    if es_1d and t1h is not None:   # superpone el motor intradía de 1h (730 días) como contraste
        roll["PF_1h"] = [_pf_ventana(t1h, pd.Timestamp(r.Inicio), pd.Timestamp(r.Fin) + pd.Timedelta(days=1))["PF"]
                         if pd.Timestamp(r.Inicio) >= pd.Timestamp(dias1h[0]["fecha"]) else np.nan
                         for r in roll.itertuples()]
    roll.to_csv(os.path.join(CARPETA, f"resultados_ventanas_rodantes{sfx}.csv"), index=False)
    comparaciones += len(roll)
    gana = (roll["PF"] > 1).to_numpy()
    r_gan, r_per = _rachas(gana), _rachas(~gana)
    print("\n" + "=" * 100)
    print(f" 3) VENTANAS RODANTES ({VENTANA_MESES} meses, paso 1 mes) | {len(roll)} ventanas SOLAPADAS (no independientes)")
    print("=" * 100)
    print(f"  Ventanas con PF>1: {gana.mean() * 100:.0f}% ({gana.sum()}/{len(roll)})")
    if r_gan:
        g = max(r_gan, key=lambda x: x[1] - x[0])
        print(f"  Racha más larga PF>1: {g[1] - g[0] + 1} ventanas ({roll['Inicio'][g[0]]} -> {roll['Fin'][g[1]]})")
        u = r_gan[-1]
        vigente = u[1] == len(roll) - 1
        print(f"  Racha ganadora más reciente: inicia en la ventana {roll['Inicio'][u[0]]}..{roll['Fin'][u[0]]}; "
              + ("sigue VIGENTE" if vigente else f"terminó en la ventana {roll['Inicio'][u[1]]}..{roll['Fin'][u[1]]}"))
    if r_per:
        p = max(r_per, key=lambda x: x[1] - x[0])
        print(f"  Racha más larga PF<1: {p[1] - p[0] + 1} ventanas ({roll['Inicio'][p[0]]} -> {roll['Fin'][p[1]]})")
    print(f"  Última ventana: PF {roll['PF'].iloc[-1]:.2f} (n={roll['N'].iloc[-1]})")

    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = pd.to_datetime(roll["Fin"])
    ax.plot(x, roll["PF"].clip(upper=3), color="tab:blue", lw=1.6, label=f"Sim. 1d SL{base[0]}/TP{base[1]}")
    if "PF_1h" in roll:
        ax.plot(x, roll["PF_1h"].clip(upper=3), color="tab:orange", lw=1.6, label="Motor intradía 1h (730d)")
    ax.axhline(1, color="black", lw=1.2, ls="--", label="PF = 1")
    ax.fill_between(x, 0, 1, color="tab:red", alpha=0.07)
    ax.set_ylim(0, 3)
    ax.set_title(f"PF en ventanas rodantes de {VENTANA_MESES} meses (paso 1 mes) - NQ=F (PF recortado a 3)")
    ax.set_xlabel("Fin de la ventana")
    ax.set_ylabel("Profit Factor")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CARPETA, f"curva_pf_vs_tiempo{sfx}.png"), dpi=120)
    plt.close(fig)

    # ---- 5) y 6) Regímenes de volatilidad y tendencia ----
    hace12 = ultimo - pd.DateOffset(months=12)
    print("\n" + "=" * 100)
    print(f" 4) RÉGIMEN DE VOLATILIDAD (ATR{ATR_PERIODO}/precio, terciles: p33={p33:.2f}% p66={p66:.2f}%)")
    print(" 5) RÉGIMEN DE TENDENCIA (retorno 20d: >+3% alcista, <-3% bajista, resto lateral)")
    print("=" * 100)
    celdas = {}
    for col, orden, archivo, titulo in (("Vol", ["baja", "media", "alta"], "pf_por_regimen_vol.png", "volatilidad"),
                                         ("Tend", ["alcista", "lateral", "bajista"], "pf_por_regimen_tendencia.png", "tendencia")):
        filas = []
        for reg_n in orden:
            for nom, ini in (("Histórico", d1.index[0]), ("Últimos 12m", hace12)):
                s = tb[(tb[col] == reg_n) & (tb["Fecha"] >= ini)]
                m = metricas_pts(s["Pts"])
                filas.append({"Régimen": reg_n, "Periodo": nom, **m, "Nota": nota_n(m["N"])})
                if nom == "Últimos 12m":
                    celdas[(col, reg_n)] = m
        t = pd.DataFrame(filas)
        comparaciones += len(t)
        print(f"\n--- Por {titulo} ---")
        print(t[["Régimen", "Periodo", "N", "WR", "PF", "Neto_pts", "MaxDD_pts", "Nota"]].round(2).to_string(index=False))
        fig, ax = plt.subplots(figsize=(8, 5))
        w = 0.38
        for k, nom in enumerate(("Histórico", "Últimos 12m")):
            sub = t[t["Periodo"] == nom].reset_index(drop=True)
            barras = ax.bar(np.arange(len(orden)) + (k - 0.5) * w, sub["PF"].fillna(0).clip(upper=3), w,
                            label=nom, color=("tab:blue", "tab:orange")[k])
            for b, (_, r) in zip(barras, sub.iterrows()):
                if r["N"] < MIN_N_SIGNIF:
                    b.set_hatch("//")
                    b.set_alpha(0.45)
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"n={int(r['N'])}", ha="center", fontsize=8)
        ax.axhline(1, color="black", ls="--", lw=1.2)
        ax.set_xticks(range(len(orden)))
        ax.set_xticklabels(orden)
        ax.set_ylabel("Profit Factor (recortado a 3)")
        ax.set_title(f"PF por régimen de {titulo} (rayado = n<20, no significativo)")
        ax.legend()
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(os.path.join(CARPETA, archivo.replace(".png", f"{sfx}.png")), dpi=120)
        plt.close(fig)

    # ---- 7) Validación cruzada de ventanas ----
    print("\n" + "=" * 100)
    print(" 6) VALIDACIÓN CRUZADA: mejor variante SL/TP en IS (por PF, n>=20) -> ¿gana en el periodo siguiente (OOS)?")
    print("=" * 100)
    cortes = [("2018-2020", "2018-01-01", "2021-01-01", "2021-2022", "2023-01-01"),
              ("2020-2022", "2020-01-01", "2023-01-01", "2023-2024", "2025-01-01"),
              ("2022-2024", "2022-01-01", "2025-01-01", "2025-hoy", "2100-01-01")]
    if not es_1d:
        print(" (no aplica en fuente 1h: solo cubre ~2024-2026, no hay periodos IS 2018-2022)")
        cortes = []
    filas, n_oos_ok = [], 0
    for nom_is, i0, i1, nom_oos, o1 in cortes:
        res_is = {v: _pf_ventana(trades[v], i0, i1) for v in VARIANTES_REG}
        res_oos = {v: _pf_ventana(trades[v], i1, o1) for v in VARIANTES_REG}
        cand = [v for v in VARIANTES_REG if res_is[v]["N"] >= MIN_N_SIGNIF]
        if not cand:
            continue
        mejor = max(cand, key=lambda v: res_is[v]["PF"])
        rank_oos = sorted(VARIANTES_REG, key=lambda v: -np.nan_to_num(res_oos[v]["PF"])).index(mejor) + 1
        n_oos_ok += res_oos[mejor]["PF"] > 1
        filas.append({"IS": nom_is, "Mejor_IS": f"SL{mejor[0]}/TP{mejor[1]}", "PF_IS": res_is[mejor]["PF"],
                      "N_IS": res_is[mejor]["N"], "OOS": nom_oos, "PF_OOS": res_oos[mejor]["PF"],
                      "N_OOS": res_oos[mejor]["N"], "Rank_OOS(de 4)": rank_oos,
                      "Nota_OOS": nota_n(res_oos[mejor]["N"])})
        comparaciones += len(VARIANTES_REG) * 2
    if filas:
        print(pd.DataFrame(filas).round(2).to_string(index=False))
        print(f"  El mejor IS gana (PF>1) en OOS en {n_oos_ok}/{len(filas)} casos.")

    # ---- 8) Últimos 24 / 12 / 6 meses ----
    print("\n" + "=" * 100)
    print(" 7) ÚLTIMOS 24 / 12 / 6 MESES (todas las variantes; 1h = motor intradía real)")
    print("=" * 100)
    filas = []
    for meses in (24, 12, 6):
        ini = ultimo - pd.DateOffset(months=meses)
        fila = {"Periodo": f"{meses}m"}
        for v in VARIANTES_REG:
            m = _pf_ventana(trades[v], ini, ultimo + pd.Timedelta(days=1))
            fila[f"PF_{v[0]}/{v[1]}"], fila[f"N_{v[0]}/{v[1]}"] = m["PF"], m["N"]
        if es_1d:
            fila["PF_pesim(base)"] = _pf_ventana(tbp, ini, ultimo + pd.Timedelta(days=1))["PF"]
            fila["PF_escal(base)"] = _pf_ventana(tbn, ini, ultimo + pd.Timedelta(days=1))["PF"]
        if es_1d and t1h is not None:
            m1 = _pf_ventana(t1h, ini, ultimo + pd.Timedelta(days=1))
            fila["PF_1h(base)"], fila["N_1h"] = m1["PF"], m1["N"]
        filas.append(fila)
    comparaciones += len(filas) * (len(VARIANTES_REG) + 3)
    print(pd.DataFrame(filas).round(2).to_string(index=False))
    m12 = _pf_ventana(tb, hace12, ultimo + pd.Timedelta(days=1))
    print(f"\n  Base SL{base[0]}/TP{base[1]} últimos 12m: PF {m12['PF']:.2f} | n={m12['N']} | neto {m12['Neto_pts']:.0f} pts")

    # ---- Conclusión automática ----
    print("\n" + "=" * 100)
    print(" CONCLUSIÓN AUTOMÁTICA (últimos 12 meses, config base)")
    print("=" * 100)
    cel = {k: v for k, v in celdas.items() if v["N"] > 0}
    todos_menor1 = all(v["PF"] < 1 for v in cel.values()) and m12["PF"] < 1
    buenos = [(k, v) for k, v in cel.items() if v["PF"] > 1.2 and v["N"] >= MIN_N_SIGNIF]
    if calib_ok is not True:
        motivo = "no se pudo calibrar" if calib_ok is None else "la calibración contra el motor 5m FALLA"
        print(f" >>> SIN VEREDICTO: la fuente '{fuente}' no es fiable ({motivo}).")
        print("     Las reglas automáticas (PF<1 en todos los regímenes, etc.) se aplicarían sobre trades que no")
        print("     representan lo que haría la estrategia con ejecución intradía real. Abajo, lo que ARROJARÍAN")
        print(f"     esas reglas, solo como referencia: PF 12m {m12['PF']:.2f}; "
              f"{'PF<1 en todos los regímenes' if todos_menor1 else 'no todos los regímenes <1'}.")
    elif todos_menor1:
        print(" >>> La estrategia ha dejado de funcionar. No operar.")
        print(f"     PF<1 en los últimos 12m global ({m12['PF']:.2f}) y en TODOS los regímenes con trades.")
    elif buenos:
        txt = ", ".join(f"{k[0]}={k[1]} (PF {v['PF']:.2f}, n={v['N']})" for k, v in buenos)
        print(f" >>> La estrategia funciona solo en: {txt}.")
        print("     Operar solo cuando se cumpla esa condición... PERO ver advertencia: es el mejor de 6 celdas, con")
        print("     el mismo periodo usado para elegirlo (selección post-hoc). Confirmar en datos nuevos antes de operar.")
    else:
        print(" >>> Sin evidencia de edge consistente. El pasado positivo puede ser suerte. No operar.")
        print(f"     Últimos 12m: PF {m12['PF']:.2f}; celdas PF>1.2 con n>=20: ninguna.")
    print(f"\n ADVERTENCIA DE COMPARACIONES MÚLTIPLES: se hicieron ~{comparaciones} comparaciones de PF "
          f"(años, semestres, trimestres, ventanas, regímenes, variantes).")
    print(f" Con {comparaciones} pruebas esperamos ~{comparaciones * 0.05:.0f} resultados 'positivos' por azar al 5%. "
          "Solo considerar edge")
    print(" si hay consistencia temporal (muchos periodos seguidos, validación OOS), no picos aislados.")
    print(" Las ventanas rodantes están solapadas: su % de PF>1 NO equivale a observaciones independientes.")
    print(f"\nArchivos en ./{CARPETA}/: resultados_regimen_anual.csv, resultados_regimen_semestral.csv, "
          "resultados_ventanas_rodantes.csv, curva_pf_vs_tiempo.png, pf_por_regimen_vol.png, "
          f"pf_por_regimen_tendencia.png | datos en ./{CARPETA_DATOS}/")
    sys.stdout.flush()


def main_movimiento():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    df = descargar_datos(TICKER_PRINCIPAL)
    if df is None:
        sys.exit(1)
    dias = preparar_dias(df)
    print(f"Días simulables: {len(dias)} ({dias[0]['fecha']} -> {dias[-1]['fecha']})")
    analisis_movimiento_real(dias)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "movimiento":
        main_movimiento()
    elif len(sys.argv) > 1 and sys.argv[1] == "regimen":
        analisis_regimen("1d")
        analisis_regimen("1h")
    elif len(sys.argv) > 1 and sys.argv[1] == "filtros":
        test_filtros_contexto()
    else:
        main()
