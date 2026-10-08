"""
ESTRATEGIAS Y FILTROS.

Una estrategia recibe el DataFrame con indicadores (ver indicadores.agregar_indicadores)
y devuelve una lista de `Senal` (fecha/hora, dirección, precio de entrada).
La entrada se simula al CIERRE de la vela de la señal (igual que el motor original).

Un filtro ex-ante es una función vela -> (¿permitido LONG?, ¿permitido SHORT?) que solo usa
indicadores causales de esa misma vela; se aplica sobre las señales antes de simular.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd

import pdh_pdl_lab as lab
import config as cfg_defecto


@dataclass
class Senal:
    ts: pd.Timestamp     # fecha/hora de la vela de señal
    direccion: int       # +1 LONG, -1 SHORT
    precio: float        # precio de entrada (cierre de la vela)


def _a_senales(df, mask_long, mask_short):
    """Convierte máscaras booleanas (alineadas con df) en lista de Senal ordenada. Si ambas, gana SHORT
    (misma prioridad que el motor original con PDH/PDL)."""
    mask_short = np.asarray(mask_short, bool)
    mask_long = np.asarray(mask_long, bool) & ~mask_short
    idx = np.where(mask_long | mask_short)[0]
    cierres = df["Close"].to_numpy(float)
    return [Senal(df.index[i], -1 if mask_short[i] else 1, float(cierres[i])) for i in idx]


class Estrategia(ABC):
    """Clase base. Subclases: definir `nombre` y `generar_senales(df)`."""
    nombre = "base"

    @abstractmethod
    def generar_senales(self, df):
        """df con indicadores -> lista de Senal."""


class EstrategiaPDH_PDL(Estrategia):
    """Toque del máximo del día anterior -> SHORT; toque del mínimo -> LONG (reversión)."""
    nombre = "PDH_PDL"

    def __init__(self, tolerancia_pct=lab.TOLERANCIA_PCT):
        self.tol = tolerancia_pct

    def generar_senales(self, df):
        pdh, pdl = df["PDH"].to_numpy(float), df["PDL"].to_numpy(float)
        toca_pdh = df["High"].to_numpy(float) >= pdh * (1 - self.tol)   # NaN (1er día) -> False
        toca_pdl = (~toca_pdh) & (df["Low"].to_numpy(float) <= pdl * (1 + self.tol))
        return _a_senales(df, toca_pdl, toca_pdh)


class EstrategiaORB(Estrategia):
    """
    Opening Range Breakout: rango (máx/mín) de los primeros `minutos` de la sesión.
    Cierre por encima del máximo -> LONG; por debajo del mínimo -> SHORT. Primera ruptura
    de cada dirección por día. Con velas más largas que `minutos` (ej. 1h) el rango es la 1ª vela.
    """
    nombre = "ORB"

    def __init__(self, minutos=cfg_defecto.ORB_MINUTOS):
        self.minutos = minutos

    def generar_senales(self, df):
        minuto = (df.index.hour * 60 + df.index.minute).to_numpy()
        # Apertura = primera vela disponible de cada sesión (09:30 en 5m/15m/30m; en las velas
        # de 1h de yfinance la de 09:30 no existe y la primera es la de 10:00)
        primera = pd.Series(minuto).groupby(df["Date"].to_numpy()).transform("min").to_numpy()
        en_rango = minuto < primera + self.minutos
        # Los primeros `minutos` definen el rango; las señales empiezan en la vela siguiente
        rango = df[en_rango]
        orh = df["Date"].map(rango.groupby("Date")["High"].max()).to_numpy(float)
        orl = df["Date"].map(rango.groupby("Date")["Low"].min()).to_numpy(float)
        # Una vela solo opera si empieza cuando el rango ya terminó (no usa velas parcialmente futuras)
        fin_rango = df["Date"].map(rango.assign(m=minuto[en_rango]).groupby("Date")["m"].max()).to_numpy(float)
        c = df["Close"].to_numpy(float)
        valida = minuto > fin_rango
        rompe_up, rompe_dn = valida & (c > orh), valida & (c < orl)
        # solo la primera ruptura de cada dirección por día
        fechas = df["Date"].to_numpy()
        primera_up = pd.Series(rompe_up).groupby(fechas).cumsum().to_numpy() == 1
        primera_dn = pd.Series(rompe_dn).groupby(fechas).cumsum().to_numpy() == 1
        return _a_senales(df, rompe_up & primera_up, rompe_dn & primera_dn)


class EstrategiaVWAP(Estrategia):
    """
    Cruce del precio con el VWAP diario: cierre cruza de abajo a arriba -> LONG, de arriba a
    abajo -> SHORT (seguimiento de tendencia). `invertir=True` opera al revés (reversión).
    """
    def __init__(self, invertir=False):
        self.invertir = invertir
        self.nombre = "VWAP_inv" if invertir else "VWAP"

    def generar_senales(self, df):
        c, v = df["Close"], df["VWAP"]
        cruce_up = ((c.shift(1) <= v.shift(1)) & (c > v)).to_numpy()
        cruce_dn = ((c.shift(1) >= v.shift(1)) & (c < v)).to_numpy()
        # no se cruza con la vela previa de OTRO día
        mismo_dia = (df["Date"] == df["Date"].shift(1)).to_numpy()
        cruce_up, cruce_dn = cruce_up & mismo_dia, cruce_dn & mismo_dia
        if self.invertir:
            cruce_up, cruce_dn = cruce_dn, cruce_up
        return _a_senales(df, cruce_up, cruce_dn)


# ==============================================================================
# FILTROS EX-ANTE
# ==============================================================================
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
    """Catálogo de filtros por defecto (umbrales en config.py)."""
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
