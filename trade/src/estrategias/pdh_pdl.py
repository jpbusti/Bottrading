"""Estrategia PDH/PDL: reversión en el máximo/mínimo del día anterior (versión original y versión sin gaps)."""
import numpy as np

from scripts import pdh_pdl_lab as lab
from src.estrategias.base import Estrategia, _a_senales


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


class EstrategiaPDH_PDL_SinGap(EstrategiaPDH_PDL):
    """
    PDH/PDL que solo acepta toques REALES, es decir, que llegan desde dentro del rango del día anterior.
      1) Día con gap: si la apertura queda a más de `max_gap` puntos fuera de [PDL, PDH]
         (por encima del PDH o por debajo del PDL), se descarta todo el día.
      2) Desde dentro: la vela anterior debe haber cerrado dentro de [PDL, PDH]. Así solo cuenta el
         primer cruce del nivel; si el precio ya estaba fuera (ruptura) no hay señal hasta que
         vuelva a entrar al rango y lo toque de nuevo.
    """
    nombre = "PDH_PDL_sin_gap"

    def __init__(self, max_gap=50.0, tolerancia_pct=lab.TOLERANCIA_PCT):
        super().__init__(tolerancia_pct)
        self.max_gap = max_gap

    def mascaras(self, df):
        """Devuelve (toca_pdh, toca_pdl, gap_dia, desde_dentro): arrays booleanos alineados con df."""
        pdh, pdl = df["PDH"].to_numpy(float), df["PDL"].to_numpy(float)
        toca_pdh = df["High"].to_numpy(float) >= pdh * (1 - self.tol)
        toca_pdl = (~toca_pdh) & (df["Low"].to_numpy(float) <= pdl * (1 + self.tol))
        apertura = df.groupby("Date")["Open"].transform("first").to_numpy(float)
        gap_dia = (apertura > pdh + self.max_gap) | (apertura < pdl - self.max_gap)
        cierre_prev = df["Close"].shift(1).to_numpy(float)   # 1ª vela del día: cierre de la sesión anterior
        desde_dentro = (cierre_prev <= pdh) & (cierre_prev >= pdl)
        return toca_pdh, toca_pdl, gap_dia, desde_dentro

    def generar_senales(self, df):
        toca_pdh, toca_pdl, gap_dia, desde_dentro = self.mascaras(df)
        ok = desde_dentro & ~gap_dia
        return _a_senales(df, toca_pdl & ok, toca_pdh & ok)
