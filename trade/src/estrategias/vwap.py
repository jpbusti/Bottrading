"""Estrategia de cruce del VWAP diario."""
from src.estrategias.base import Estrategia, _a_senales


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
