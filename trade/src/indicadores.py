"""
INDICADORES TÉCNICOS. Todos son causales: el valor de la vela t solo usa velas <= t,
así que pueden usarse como filtro ex-ante en la señal de esa vela sin sesgo de futuro.
"""
import numpy as np
import pandas as pd


def atr(df, n=14):
    """ATR de Wilder (media exponencial alpha=1/n del True Range)."""
    cierre_prev = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - cierre_prev).abs(),
                    (df["Low"] - cierre_prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def vwap_diario(df):
    """VWAP acumulado desde la apertura de cada sesión (precio típico x volumen).
    Si un activo no trae volumen, degrada a la media acumulada del precio típico."""
    tipico = (df["High"] + df["Low"] + df["Close"]) / 3
    vol = df["Volume"].fillna(0)
    dia = df["Date"]
    pv = (tipico * vol).groupby(dia).cumsum()
    v = vol.groupby(dia).cumsum()
    vwap = pv / v.replace(0, np.nan)
    media = tipico.groupby(dia).expanding().mean().reset_index(level=0, drop=True)
    return vwap.fillna(media)


def rsi(cierre, n=14):
    """RSI de Wilder."""
    d = cierre.diff()
    ganancia = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    perdida = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = ganancia / perdida.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0).where(ganancia.notna())


def bollinger(cierre, n=20, k=2.0):
    """Devuelve (media, banda superior, banda inferior, %B)."""
    media = cierre.rolling(n).mean()
    desv = cierre.rolling(n).std(ddof=0)
    sup, inf = media + k * desv, media - k * desv
    pctb = (cierre - inf) / (sup - inf).replace(0, np.nan)
    return media, sup, inf, pctb


def agregar_indicadores(df, config):
    """Devuelve una copia del DataFrame con ATR, ATR_ratio, VWAP, RSI, Bollinger, PDH y PDL."""
    df = df.copy()
    df["ATR"] = atr(df, config.ATR_PERIODO)
    # ATR relativo a su propia media reciente -> comparable entre temporalidades y épocas
    base = df["ATR"].rolling(config.ATR_VENTANA_REL, min_periods=config.ATR_VENTANA_REL // 5).mean()
    df["ATR_ratio"] = df["ATR"] / base
    df["VWAP"] = vwap_diario(df)
    df["RSI"] = rsi(df["Close"], config.RSI_PERIODO)
    df["BB_mid"], df["BB_up"], df["BB_low"], df["BB_pctb"] = bollinger(df["Close"], config.BB_PERIODO, config.BB_DESV)
    # PDH/PDL = máximo/mínimo de la sesión anterior (misma definición que el laboratorio)
    diario = df.groupby("Date").agg(H=("High", "max"), L=("Low", "min"))
    df["PDH"] = df["Date"].map(diario["H"].shift(1))
    df["PDL"] = df["Date"].map(diario["L"].shift(1))
    return df
