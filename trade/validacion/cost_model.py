"""Modelo de costos por contrato y POR ANIO (comision + slippage + spread), en dolares y en puntos.

PROCEDENCIA DE LOS VALORES (leer antes de usar)
  - Tabla IBKR (`TABLA_IBKR`, la que usa `costo_trade` por defecto): valores dictados por el usuario (Juan) en el hilo
    del proyecto el 2026-10-08 (comisiones y slippage como "costos de Interactive Brokers"; spread por lado en un
    segundo mensaje del mismo dia). NO se han contrastado con el contrato ni con el extracto de la cuenta: toda fila
    lleva `[VERIFICAR CON IBKR]` hasta que el usuario confirme los fees exactos (IBKR + exchange + regulatorios + NFA).
  - Anios 2024-2026: valores dictados tal cual (`NOTA_BASE`).
  - Anios 2016-2023: NO hay dato historico. Se usa, componente a componente, el MAYOR entre lo dictado y el supuesto de
    LSR v1 (NQ/ES), y se marcan con `NOTA_PREVIO` ([VERIFICAR]); GC/BTC/MBT repiten lo dictado. Es una cota prudente,
    no un dato real: las comisiones y fees de exchange han subido con el tiempo.
  - Componentes de un trade redondo (entrada + salida): comision RT + slippage (1 tick/lado x 2) + spread (1 tick/lado x 2).
    Slippage y spread se suman a proposito (metodologia del proyecto); es un supuesto conservador [VERIFICAR].
  - `TABLA_LSR_V1`: supuestos originales del pre-registro LSR v1 (motor_lsr.costo_pts), conservados para reproducir
    resultados historicos. Con spread incluido, los costos NQ/ES nuevos son >= a los de LSR v1 (ver tests).
  - Ultima actualizacion de los valores: 2026-10-08.

BTC y MBT: [NO USAR HASTA VERIFICAR]. Estan cargados con los datos dictados, pero `costo_trade` lanza error salvo que se
  pase `permitir_no_verificado=True`. Dudas conocidas (no se "corrigieron" en silencio):
  - BTC (CME, 5 BTC): tick $5.00 por bitcoin = $25.00 por tick. El slippage dictado ($5.00 por lado) NO equivale a
    1 tick ($25.00): inconsistencia pendiente.
  - MBT (0.1 BTC): se cargo lo dictado (tick $0.50 por bitcoin = $0.05). Segun mi conocimiento de CME el tick del MBT
    es $5.00 por bitcoin = $0.50 por contrato; es decir, lo dictado seria 10x menor. Verificar en la ficha de CME.
"""
from __future__ import annotations

from dataclasses import dataclass

ESTADO = "[VERIFICAR CON IBKR]"
NO_USAR = "[NO USAR HASTA VERIFICAR]"
NOTA_BASE = "valores dictados por el usuario 2026-10-08 (IBKR), sin confirmar con la cuenta"
NOTA_PREVIO = "[VERIFICAR] sin dato historico: se asume igual a 2024-2026"
ANIO_INI, ANIO_FIN, ANIO_BASE_DESDE = 2016, 2026, 2024


# ---------------------------------------------------------------- contratos
@dataclass(frozen=True)
class Contrato:
    sym: str
    punto_valor: float      # USD por 1.0 punto de precio
    tick_pts: float         # tamano del tick en puntos
    tick_usd: float         # USD por tick
    usable: bool = True


CONTRATOS: dict[str, Contrato] = {
    "NQ": Contrato("NQ", 20.0, 0.25, 5.00),
    "ES": Contrato("ES", 50.0, 0.25, 12.50),
    "GC": Contrato("GC", 100.0, 0.10, 10.00),
    "BTC": Contrato("BTC", 5.0, 5.00, 25.00, usable=False),    # 5 BTC; tick $5/BTC = $25
    "MBT": Contrato("MBT", 0.1, 0.50, 0.05, usable=False),     # 0.1 BTC; valores dictados (ver nota)
}
VALOR_PUNTO = {k: v.punto_valor for k, v in CONTRATOS.items()}


# ---------------------------------------------------------------- tabla por anio
@dataclass(frozen=True)
class CostoAnio:
    inst: str
    anio: int
    comision_usd_rt: float        # ida y vuelta, por contrato
    slippage_usd_lado: float      # USD por lado (1 tick)
    spread_usd_lado: float        # USD por lado (1 tick de spread) [VERIFICAR]
    estado: str = ESTADO
    nota: str = NOTA_BASE

    @property
    def slippage_usd_rt(self) -> float:
        return 2 * self.slippage_usd_lado

    @property
    def spread_usd_rt(self) -> float:
        return 2 * self.spread_usd_lado

    @property
    def total_usd(self) -> float:
        return self.comision_usd_rt + self.slippage_usd_rt + self.spread_usd_rt

    @property
    def total_pts(self) -> float:
        return self.total_usd / CONTRATOS[self.inst].punto_valor


# ---------------------------------------------------------------- tabla LEGADA (LSR v1)
def _legado() -> dict[tuple[str, int], CostoAnio]:
    """Reproduce exactamente motor_lsr.costo_pts original: slippage 0.50 pts RT + spread por anio + comision RT."""
    t = {}
    for a in range(ANIO_INI, ANIO_FIN + 1):
        sp_nq = 0.50 if a <= 2019 else (0.75 if a == 2020 else 0.375)    # pts ida y vuelta
        sp_es = 0.375 if a == 2020 else 0.25
        t[("NQ", a)] = CostoAnio("NQ", a, 4.50, 0.25 * 20.0, sp_nq * 20.0 / 2, "[VERIFICAR]", "supuesto LSR v1")
        t[("ES", a)] = CostoAnio("ES", a, 4.50, 0.25 * 50.0, sp_es * 50.0 / 2, "[VERIFICAR]", "supuesto LSR v1")
    return t


TABLA_LSR_V1 = _legado()


# inst: (comision RT USD, slippage USD/lado, spread USD/lado)
#   NQ: spread 0.25 pts x $20 = $5.00 | ES: 0.25 pts x $50 = $12.50 | GC: 0.10 pts x $100 = $10.00
#   BTC: 1 tick = $25.00 | MBT: $0.05 (dictado)
_BASE = {"NQ": (4.30, 5.00, 0.25 * 20.0), "ES": (4.30, 12.50, 0.25 * 50.0), "GC": (4.30, 10.00, 0.10 * 100.0),
         "BTC": (15.00, 5.00, 25.00), "MBT": (7.50, 0.10, 0.05)}


def _construir(base=_BASE) -> dict[tuple[str, int], CostoAnio]:
    """2024-2026: valores dictados. Anios previos: para cada componente (comision, slippage, spread) el MAYOR entre lo
    dictado y lo que asumia LSR v1 (solo NQ/ES). Asi un anio previo nunca queda mas barato que LSR v1 (p.ej. el
    spread ampliado de 2020). Todo `[VERIFICAR]` hasta tener historico real."""
    t = {}
    for inst, (com, slip, spr) in base.items():
        for a in range(ANIO_INI, ANIO_FIN + 1):
            c_com, c_slip, c_spr, nota = com, slip, spr, NOTA_BASE
            if a < ANIO_BASE_DESDE:
                nota = NOTA_PREVIO
                leg = TABLA_LSR_V1.get((inst, a))
                if leg is not None:
                    c_com, c_slip, c_spr = (max(com, leg.comision_usd_rt), max(slip, leg.slippage_usd_lado),
                                            max(spr, leg.spread_usd_lado))
                    nota += " (componentes = max(dictado, supuesto LSR v1))"
            estado = ESTADO if CONTRATOS[inst].usable else f"{ESTADO} {NO_USAR}"
            t[(inst, a)] = CostoAnio(inst, a, c_com, c_slip, c_spr, estado, nota)
    return t


# EDITAR AQUI cuando confirmes los fees reales de tu cuenta (por instrumento y anio).
TABLA_IBKR: dict[tuple[str, int], CostoAnio] = _construir()


def costo_anio(inst: str, anio: int, tabla=None, permitir_no_verificado: bool = False) -> CostoAnio:
    if tabla is None and not CONTRATOS[inst].usable and not permitir_no_verificado:
        raise ValueError(f"{inst} {NO_USAR}: pasa permitir_no_verificado=True solo para inspeccionar")
    tabla = TABLA_IBKR if tabla is None else tabla
    try:
        return tabla[(inst, anio)]
    except KeyError:
        raise KeyError(f"sin costos para {inst} {anio}") from None


def costo_trade(inst: str, anio: int, n_contratos: int = 1, tabla=None, permitir_no_verificado: bool = False) -> dict:
    """Costo de UN trade redondo (entrada + salida) en USD y en puntos, desglosado (comision + slippage + spread)."""
    c = costo_anio(inst, anio, tabla, permitir_no_verificado)
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
