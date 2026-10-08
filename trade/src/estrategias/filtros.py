"""
FILTROS EX-ANTE sobre las señales de cualquier estrategia.

Un filtro es una función vela -> (¿permitido LONG?, ¿permitido SHORT?) que solo usa
indicadores causales de esa misma vela; se aplica sobre las señales antes de simular.
"""
import numpy as np

from config import config as cfg_defecto


class Filtro:
    """nombre + función df -> (ok_long, ok_short) como arrays booleanos. NaN en el indicador => no opera."""
    def __init__(self, nombre, fn):
        self.nombre, self.fn = nombre, fn

    def mascaras(self, df):
        ok_l, ok_s = self.fn(df)
        return np.asarray(ok_l, bool), np.asarray(ok_s, bool)


def _todo(df):
    t = np.ones(len(df), bool)
    return t, t


def crear_filtros(config=cfg_defecto):
    """Catálogo de filtros por defecto (umbrales en config/config.py)."""
    def atr_alto(df):    # volatilidad por encima de su media reciente
        m = (df["ATR_ratio"] > 1.0).to_numpy()
        return m, m

    def atr_bajo(df):
        m = (df["ATR_ratio"] < 1.0).to_numpy()
        return m, m

    def vwap_favor(df):  # a favor: LONG sobre VWAP, SHORT bajo VWAP
        return (df["Close"] > df["VWAP"]).to_numpy(), (df["Close"] < df["VWAP"]).to_numpy()

    def vwap_contra(df):  # en contra (reversión): LONG bajo VWAP, SHORT sobre VWAP
        return (df["Close"] < df["VWAP"]).to_numpy(), (df["Close"] > df["VWAP"]).to_numpy()

    def rsi_extremo(df):  # agotamiento: LONG con RSI bajo, SHORT con RSI alto
        return ((df["RSI"] < config.FILTRO_RSI_BAJO).to_numpy(),
                (df["RSI"] > config.FILTRO_RSI_ALTO).to_numpy())

    def bb_extremo(df):   # cerca de la banda inferior/superior de Bollinger
        return ((df["BB_pctb"] < config.FILTRO_BB_BAJO).to_numpy(),
                (df["BB_pctb"] > config.FILTRO_BB_ALTO).to_numpy())

    return [Filtro("sin_filtro", _todo), Filtro("atr_alto", atr_alto), Filtro("atr_bajo", atr_bajo),
            Filtro("vwap_favor", vwap_favor), Filtro("vwap_contra", vwap_contra),
            Filtro("rsi_extremo", rsi_extremo), Filtro("bb_extremo", bb_extremo)]


def aplicar_filtro(df, senales, filtro):
    """Deja solo las señales permitidas por el filtro en la vela de la señal."""
    if filtro is None or filtro.nombre == "sin_filtro":
        return senales
    ok_l, ok_s = filtro.mascaras(df)
    pos = df.index.get_indexer([s.ts for s in senales])
    return [s for s, i in zip(senales, pos) if (ok_l[i] if s.direccion == 1 else ok_s[i])]
