"""Modelo de costos por contrato y POR ANIO (comision + slippage + spread), en dolares y en puntos.

PROCEDENCIA DE LOS VALORES (leer antes de usar)
  - Tabla IBKR (`TABLA_IBKR`, la que usa `costo_trade` por defecto): valores que el usuario (Juan) dicta como
    "costos de Interactive Brokers" en el hilo del proyecto el 2026-10-08. NO se han contrastado con el contrato
    ni con el extracto de su cuenta. Cada fila lleva el estado `[VERIFICAR CON IBKR]` hasta que el usuario confirme los
    fees exactos (comision IBKR + exchange + regulatorios + NFA).
  - Anios 2024-2026: se usan los valores dictados tal cual (`NOTA_BASE`).
  - Anios 2016-2023: NO hay dato historico de IBKR. Se asumen IGUALES a 2024-2026 y se marcan con `NOTA_PREVIO`
    ([VERIFICAR]). No es una estimacion real: las comisiones y fees de exchange han subido con el tiempo, asi que los
    backtests de esos anios pueden estar optimistas. Reemplazar cuando haya un historico real (estados de cuenta).
  - Spread: no fue dictado -> `spread_usd_rt = 0.0` ([VERIFICAR]). El slippage de 1 tick por lado se considera que ya
    incluye el cruce de spread de una orden a mercado. La tabla legada de LSR v1 SI sumaba 0.25-0.75 pts de spread
    (ver `TABLA_LSR_V1`), por eso los costos nuevos son ~40% menores: backtests nuevos y LSR v1 NO son comparables sin
    elegir la misma tabla.
  - `TABLA_LSR_V1`: supuestos originales del pre-registro LSR v1 (motor_lsr.costo_pts), conservados para reproducir
    resultados historicos. Fuente: supuesto del proyecto, marcados [VERIFICAR] en el motor original.
  - Ultima actualizacion de los valores: 2026-10-08 (mensaje del usuario en el hilo del proyecto).

NOTAS DE ESPECIFICACION (a verificar; NO se corrigieron los valores dictados)
  - BTC (CME) y MBT: los datos dictados son internamente inconsistentes con las especificaciones CME que conozco
    (BTC: multiplicador 5 BTC, tick $5 por BTC = $25; MBT: multiplicador 0.1 BTC, tick $5 por BTC = $0.50). Se guardan
    tal cual, con `punto_valor` segun mi conocimiento de CME ([VERIFICAR]). Solo NQ y ES estan cubiertos por tests.
"""
from __future__ import annotations

from dataclasses import dataclass

ESTADO = "[VERIFICAR CON IBKR]"
NOTA_BASE = "valores dictados por el usuario 2026-10-08 (IBKR), sin confirmar con la cuenta"
NOTA_PREVIO = "[VERIFICAR] sin dato historico: se asume igual a 2024-2026"
ANIO_INI, ANIO_FIN, ANIO_BASE_DESDE = 2016, 2026, 2024


# ---------------------------------------------------------------- contratos
@dataclass(frozen=True)
class Contrato:
    sym: str
    punto_valor: float      # USD por 1.0 punto de precio
    tick_pts: float         # tamano del tick en puntos
    tick_usd: float         # USD por tick (dictado por el usuario donde aplica)


CONTRATOS: dict[str, Contrato] = {
    "NQ": Contrato("NQ", 20.0, 0.25, 5.00),
    "ES": Contrato("ES", 50.0, 0.25, 12.50),
    "GC": Contrato("GC", 100.0, 0.10, 10.00),
    "BTC": Contrato("BTC", 5.0, 5.00, 5.00),      # [VERIFICAR] ver nota; tick_usd dictado = $5.00
    "MBT": Contrato("MBT", 0.1, 1.00, 1.00),      # [VERIFICAR] ver nota; tick_pts dictado = $1.00
}
VALOR_PUNTO = {k: v.punto_valor for k, v in CONTRATOS.items()}


# ---------------------------------------------------------------- tabla por anio
@dataclass(frozen=True)
class CostoAnio:
    inst: str
    anio: int
    comision_usd_rt: float        # ida y vuelta, por contrato
    slippage_usd_lado: float      # USD por lado (1 tick)
    spread_usd_rt: float = 0.0    # ida y vuelta, por contrato [VERIFICAR]
    estado: str = ESTADO
    nota: str = NOTA_BASE

    @property
    def slippage_usd_rt(self) -> float:
        return 2 * self.slippage_usd_lado

    @property
    def total_usd(self) -> float:
        return self.comision_usd_rt + self.slippage_usd_rt + self.spread_usd_rt

    @property
    def total_pts(self) -> float:
        return self.total_usd / CONTRATOS[self.inst].punto_valor


# Base dictada (IBKR): comision RT por contrato, slippage USD por lado (1 tick)
_BASE = {"NQ": (4.30, 5.00), "ES": (4.30, 12.50), "GC": (4.30, 10.00), "BTC": (15.00, 5.00), "MBT": (7.50, 0.10)}


def _construir(base=_BASE) -> dict[tuple[str, int], CostoAnio]:
    t = {}
    for inst, (com, slip) in base.items():
        for a in range(ANIO_INI, ANIO_FIN + 1):
            nota = NOTA_BASE if a >= ANIO_BASE_DESDE else NOTA_PREVIO
            t[(inst, a)] = CostoAnio(inst, a, com, slip, 0.0, ESTADO, nota)
    return t


# EDITAR AQUI cuando confirmes los fees reales de tu cuenta (por instrumento y anio).
TABLA_IBKR: dict[tuple[str, int], CostoAnio] = _construir()


def costo_anio(inst: str, anio: int, tabla=None) -> CostoAnio:
    tabla = TABLA_IBKR if tabla is None else tabla
    try:
        return tabla[(inst, anio)]
    except KeyError:
        raise KeyError(f"sin costos para {inst} {anio}") from None


def costo_trade(inst: str, anio: int, n_contratos: int = 1, tabla=None) -> dict:
    """Costo de UN trade redondo (entrada + salida) en USD y en puntos, desglosado.
    Solo NQ/ES estan cubiertos por tests; los demas usan los datos dictados."""
    c = costo_anio(inst, anio, tabla)
    n = n_contratos
    return dict(inst=inst, anio=anio, contratos=n, estado=c.estado,
                comision_usd=c.comision_usd_rt * n, slippage_usd=c.slippage_usd_rt * n, spread_usd=c.spread_usd_rt * n,
                total_usd=c.total_usd * n, total_pts=c.total_pts)   # puntos son POR contrato


def costo_usd(inst: str, anio: int, tabla=None) -> float:
    return costo_anio(inst, anio, tabla).total_usd


def costo_pts(inst: str, anio: int, tabla=None) -> float:
    """Costo ida y vuelta por contrato en puntos (tabla IBKR por defecto)."""
    return costo_anio(inst, anio, tabla).total_pts


def estado_verificacion(tabla=None) -> dict:
    """Cuantas filas siguen sin verificar. Mientras `sin_verificar` no este vacio, no hay backtest 'serio'."""
    tabla = TABLA_IBKR if tabla is None else tabla
    pend = sorted({f"{c.inst} {c.anio}" for c in tabla.values() if "VERIFICAR" in c.estado})
    return dict(total=len(tabla), verificados=len(tabla) - len(pend), sin_verificar=pend)


# ---------------------------------------------------------------- tabla LEGADA (LSR v1)
def _legado() -> dict[tuple[str, int], CostoAnio]:
    """Reproduce exactamente motor_lsr.costo_pts original: slippage 0.50 pts RT + spread por anio + comision RT en pts."""
    t = {}
    for a in range(ANIO_INI, ANIO_FIN + 1):
        sp_nq = 0.50 if a <= 2019 else (0.75 if a == 2020 else 0.375)
        sp_es = 0.375 if a == 2020 else 0.25
        t[("NQ", a)] = CostoAnio("NQ", a, 4.50, 0.25 * 20.0, sp_nq * 20.0, "[VERIFICAR]", "supuesto LSR v1")
        t[("ES", a)] = CostoAnio("ES", a, 4.50, 0.25 * 50.0, sp_es * 50.0, "[VERIFICAR]", "supuesto LSR v1")
    return t


TABLA_LSR_V1 = _legado()
