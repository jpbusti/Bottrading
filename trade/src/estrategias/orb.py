"""Estrategia ORB (Opening Range Breakout)."""
import pandas as pd

from config import config as cfg_defecto
from src.estrategias.base import Estrategia, _a_senales


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
