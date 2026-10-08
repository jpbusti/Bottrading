"""
BASE DE ESTRATEGIAS: dataclass `Senal`, clase abstracta `Estrategia` y helper `_a_senales`.

Una estrategia recibe el DataFrame con indicadores (ver src.indicadores.agregar_indicadores)
y devuelve una lista de `Senal` (fecha/hora, dirección, precio de entrada).
La entrada se simula al CIERRE de la vela de la señal (igual que el motor original).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd


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
