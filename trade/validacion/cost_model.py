"""Modelo de costos ida y vuelta (round trip) en PUNTOS, por instrumento y anio.

Los valores reproducen EXACTAMENTE scripts/lsr/motor_lsr.py::costo_pts (supuestos del proyecto, SIN verificar con broker).
Cada tramo tiene `verificado=False` hasta que el usuario complete `fuente` con un dato real (extracto del broker,
tabla de comisiones, spread medido). Mientras haya tramos sin verificar, `estado_verificacion()` lo dice.

Por contrato: NQ 1 punto = $20 (tick 0.25 = $5); ES 1 punto = $50 (tick 0.25 = $12.50).
  - slippage_rt : 1 tick por lado x 2 lados = 0.50 pts (minimo exigido por la metodologia).
  - spread_rt   : medio spread pagado al entrar y al salir, expresado en pts ida y vuelta [VERIFICAR].
  - comision_rt : USD ida y vuelta por contrato / valor del punto. Hoy: NQ $4.50 RT -> 0.225 pts; ES $4.50 RT -> 0.09 pts [VERIFICAR].
"""
from __future__ import annotations

from dataclasses import dataclass

VALOR_PUNTO = {"NQ": 20.0, "ES": 50.0}


@dataclass(frozen=True)
class TramoCosto:
    inst: str
    anio_desde: int
    anio_hasta: int
    slippage_rt: float
    spread_rt: float
    comision_usd_rt: float
    verificado: bool = False
    fuente: str = "supuesto del proyecto (motor_lsr.costo_pts)"   # <- reemplazar con la fuente real

    @property
    def comision_pts(self) -> float:
        return self.comision_usd_rt / VALOR_PUNTO[self.inst]

    @property
    def total_pts(self) -> float:
        return self.slippage_rt + self.spread_rt + self.comision_pts


# -------- EDITAR AQUI cuando tengas los datos reales del broker (y poner verificado=True + fuente) --------
TABLA: tuple[TramoCosto, ...] = (
    TramoCosto("NQ", 2016, 2019, 0.50, 0.500, 4.50),
    TramoCosto("NQ", 2020, 2020, 0.50, 0.750, 4.50),
    TramoCosto("NQ", 2021, 2100, 0.50, 0.375, 4.50),
    TramoCosto("ES", 2016, 2019, 0.50, 0.250, 4.50),
    TramoCosto("ES", 2020, 2020, 0.50, 0.375, 4.50),
    TramoCosto("ES", 2021, 2100, 0.50, 0.250, 4.50),
)


def tramo(inst: str, anio: int, tabla=TABLA) -> TramoCosto:
    for t in tabla:
        if t.inst == inst and t.anio_desde <= anio <= t.anio_hasta:
            return t
    raise KeyError(f"sin tramo de costos para {inst} {anio}")


def costo_pts(inst: str, anio: int, tabla=TABLA) -> float:
    """Costo ida y vuelta en puntos (slippage + spread + comision)."""
    return tramo(inst, anio, tabla).total_pts


def costo_usd(inst: str, anio: int, tabla=TABLA) -> float:
    return costo_pts(inst, anio, tabla) * VALOR_PUNTO[inst]


def estado_verificacion(tabla=TABLA) -> dict:
    """{'verificados': n, 'sin_verificar': [...]} para bloquear/avisar antes de un backtest serio."""
    pend = [f"{t.inst} {t.anio_desde}-{min(t.anio_hasta, 2026)}" for t in tabla if not t.verificado]
    return dict(verificados=len(tabla) - len(pend), sin_verificar=pend)
