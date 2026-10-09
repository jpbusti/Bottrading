"""Modelo de costos por contrato y POR ANIO (comision + slippage + spread), en dolares y en puntos.

DOS MODOS, TABLAS SEPARADAS (no se mezclan):
  - modo="futuros" (por defecto): NQ/ES/GC/BTC/MBT de CME via IBKR -> `TABLA_IBKR` / `TABLA_LSR_V1` (abajo).
  - modo="cfd": US100 Cash / XAUUSD / BTCUSD por broker (IC Markets, Pepperstone, XM) -> `TABLA_CFD` (al final del archivo).
    La operativa real es CFD US100 Cash; el backtest corre sobre NQ como proxy de precios y el COSTO se evalua con la
    tabla CFD. Toda fila CFD es [VERIFICAR CON IC MARKETS / PEPPERSTONE] (valores dictados, sin contrastar).

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


def costo_trade(inst: str, anio: int, n_contratos: int = 1, tabla=None, permitir_no_verificado: bool = False,
                modo: str = "futuros", **kw_cfd) -> dict:
    """Costo de UN trade redondo (entrada + salida) en USD y en puntos, desglosado.

    modo="futuros": comision + slippage + spread (tabla IBKR). `n_contratos` = contratos.
    modo="cfd": spread + comision + swap (TABLA_CFD); `n_contratos` = LOTES (puede ser 0.01). kw_cfd: broker, usar_spread,
      noches, slippage_pts_lado, swap_pts_noche, spread_pts (ver `costo_trade_cfd`).
    """
    if modo == "cfd":
        return costo_trade_cfd(inst, anio, lotes=n_contratos, tabla=tabla, **kw_cfd)
    if modo != "futuros":
        raise ValueError(f"modo desconocido: {modo!r} (usa 'futuros' o 'cfd')")
    c = costo_anio(inst, anio, tabla, permitir_no_verificado)
    n = n_contratos
    return dict(inst=inst, anio=anio, contratos=n, estado=c.estado,
                comision_usd=c.comision_usd_rt * n, slippage_usd=c.slippage_usd_rt * n, spread_usd=c.spread_usd_rt * n,
                total_usd=c.total_usd * n, total_pts=c.total_pts)   # puntos son POR contrato


def costo_usd(inst: str, anio: int, tabla=None, modo: str = "futuros", **kw_cfd) -> float:
    if modo == "cfd":
        return costo_trade_cfd(inst, anio, tabla=tabla, **kw_cfd)["total_usd"]
    return costo_anio(inst, anio, tabla).total_usd


def costo_pts(inst: str, anio: int, tabla=None, modo: str = "futuros", **kw_cfd) -> float:
    """Costo ida y vuelta en puntos: futuros = por contrato (tabla IBKR por defecto); cfd = por 1 lote, puntos del indice."""
    if modo == "cfd":
        return costo_trade_cfd(inst, anio, tabla=tabla, **kw_cfd)["total_pts"]
    return costo_anio(inst, anio, tabla).total_pts


def estado_verificacion(tabla=None) -> dict:
    """Cuantas filas siguen sin verificar. Mientras `sin_verificar` no este vacio, no hay backtest 'serio'."""
    tabla = TABLA_IBKR if tabla is None else tabla
    pend = sorted({f"{c.inst} {c.anio}" for c in tabla.values() if "VERIFICAR" in c.estado})
    return dict(total=len(tabla), verificados=len(tabla) - len(pend), sin_verificar=pend)


# ====================================================================== MODO CFD (tabla SEPARADA de futuros)
# NO mezclar con TABLA_IBKR. Fuente de TODOS los valores: mensaje del usuario (Juan) 2026-10-09 (version editada).
# Todo es [VERIFICAR CON IC MARKETS / PEPPERSTONE]: no se ha contrastado con la ficha del broker ni con spreads reales.
# Spread: rango (min, max) en PUNTOS del instrumento. Para backtest conservador se usa el MAXIMO por defecto.
# Pepperstone y XM: el usuario NO dio spread de Pepperstone, ni de XM para XAUUSD/BTCUSD -> `None` (sin dato, no se
#   inventa). Un spread `None` hace que `costo_trade_cfd` falle salvo que se pase `spread_pts=` explicito.
# Swap: el usuario dijo "si aplica" sin cifras -> `None`. Trades intradia (noches=0) no pagan swap; si noches>0 hay que
#   pasar `swap_pts_noche=` o falla. Los swaps reales dependen del broker/dia (triple los miercoles) [VERIFICAR].
# Slippage CFD: no dictado -> 0.0 por defecto y el resultado marca `slippage_modelado=False`. La metodologia exige
#   modelarlo: pasa `slippage_pts_lado=` en el backtest serio.
# Tamano de contrato (USD por 1.0 punto con 1 lote): especificacion tipica, NO dictada por el usuario [VERIFICAR] en la
#   ficha del broker (algunos brokers usan $10/pt por lote en US100).
# Un solo nivel de spread por (instrumento, broker): no hay historico por anio. Aplicar el spread de hoy a 2016-2021
#   (NQ proxy) es un supuesto optimista [VERIFICAR].
BROKER_PRIORITARIO = "IC Markets"
BROKERS_CFD = ("IC Markets", "Pepperstone", "XM")
ESTADO_CFD = "[VERIFICAR CON IC MARKETS / PEPPERSTONE]"
SPREAD_ANIOS_NOTA = "spread unico (sin historico por anio) [VERIFICAR]"


@dataclass(frozen=True)
class CFD:
    sym: str                 # nombre del simbolo en el broker
    proxy: str               # instrumento de futuros usado como proxy de precios en backtest
    valor_punto_lote: float  # USD por 1.0 punto con 1 lote [VERIFICAR en la ficha del broker]


CONTRATOS_CFD: dict[str, CFD] = {
    "US100": CFD("US100 Cash", "NQ", 1.0),
    "XAUUSD": CFD("XAUUSD", "GC", 100.0),     # 1 lote = 100 oz (tipico)
    "BTCUSD": CFD("BTCUSD", "BTC", 1.0),      # 1 lote = 1 BTC (tipico)
}


@dataclass(frozen=True)
class CostoCFD:
    inst: str
    broker: str
    spread_pts_min: float | None
    spread_pts_max: float | None
    comision_usd_lote_rt: float = 0.0           # cuenta Standard: $0 (dictado)
    swap_pts_noche_long: float | None = None    # sin dato: "si aplica"
    swap_pts_noche_short: float | None = None
    estado: str = ESTADO_CFD
    nota: str = "valores dictados por el usuario 2026-10-09, sin confirmar con el broker; " + SPREAD_ANIOS_NOTA

    @property
    def tiene_spread(self) -> bool:
        return self.spread_pts_max is not None


def _cfd(inst, broker, lo=None, hi=None, nota=None):
    kw = {} if nota is None else dict(nota=nota)
    return (inst, broker), CostoCFD(inst, broker, lo, hi, **kw)


_SIN_DATO = "sin dato del usuario: NO inventado [VERIFICAR]"
TABLA_CFD: dict[tuple[str, str], CostoCFD] = dict([
    _cfd("US100", "IC Markets", 1.0, 1.5),
    _cfd("XAUUSD", "IC Markets", 0.15, 0.30),
    _cfd("BTCUSD", "IC Markets", 10.0, 50.0, "spread variable segun volatilidad (rango dictado) [VERIFICAR]"),
    _cfd("US100", "Pepperstone", nota=_SIN_DATO),
    _cfd("XAUUSD", "Pepperstone", nota=_SIN_DATO),
    _cfd("BTCUSD", "Pepperstone", nota=_SIN_DATO),
    _cfd("US100", "XM", 1.5, 2.5, "rango dictado como referencia de comparacion (no para operar) [VERIFICAR]"),
    _cfd("XAUUSD", "XM", nota=_SIN_DATO),
    _cfd("BTCUSD", "XM", nota=_SIN_DATO),
])


def costo_cfd(inst: str, broker: str = BROKER_PRIORITARIO, tabla=None) -> CostoCFD:
    tabla = TABLA_CFD if tabla is None else tabla
    try:
        return tabla[(inst, broker)]
    except KeyError:
        raise KeyError(f"sin costos CFD para {inst} / {broker}") from None


def costo_trade_cfd(inst: str, anio: int | None = None, lotes: float = 1.0, broker: str = BROKER_PRIORITARIO,
                    tabla=None, usar_spread: str = "max", noches: int = 0, slippage_pts_lado: float = 0.0,
                    swap_pts_noche: float | None = None, spread_pts: float | None = None, lado: str = "long") -> dict:
    """Costo de UN trade redondo en CFD (entrada + salida), en puntos del indice y en USD.

    - Spread: se paga UNA vez ida y vuelta (compras al ask, vendes al bid). `usar_spread` = "min" | "max" | "medio".
      `spread_pts` lo reemplaza (p.ej. spread observado en tu demo).
    - Comision: $0 en cuenta Standard (dictado) x lotes.
    - Swap: `noches` x (`swap_pts_noche` o el de la tabla); si noches>0 y no hay dato -> error (no se asume 0).
    - Slippage: 0 por defecto; el resultado marca `slippage_modelado`. `anio` solo se conserva por compatibilidad con el
      modo futuros: NO cambia el costo (no hay historico por anio).
    """
    if inst not in CONTRATOS_CFD:
        raise KeyError(f"instrumento CFD desconocido: {inst} ({sorted(CONTRATOS_CFD)})")
    c = costo_cfd(inst, broker, tabla)
    if spread_pts is None:
        if not c.tiene_spread:
            raise ValueError(f"{inst} / {broker}: sin spread cargado {ESTADO_CFD}; pasa spread_pts= explicito")
        spread_pts = {"min": c.spread_pts_min, "max": c.spread_pts_max,
                      "medio": (c.spread_pts_min + c.spread_pts_max) / 2}[usar_spread]
    swap = 0.0
    if noches > 0:
        sw = swap_pts_noche if swap_pts_noche is not None else (
            c.swap_pts_noche_long if lado == "long" else c.swap_pts_noche_short)
        if sw is None:
            raise ValueError(f"{inst} / {broker}: swap sin dato {ESTADO_CFD}; pasa swap_pts_noche= para {noches} noche(s)")
        swap = noches * sw    # >0 = costo (convencion: puntos que PAGAS por noche)
    vp = CONTRATOS_CFD[inst].valor_punto_lote
    pts = spread_pts + 2 * slippage_pts_lado + swap
    com = c.comision_usd_lote_rt * lotes
    return dict(modo="cfd", inst=inst, broker=broker, anio=anio, lotes=lotes, estado=c.estado,
                spread_pts=spread_pts, slippage_pts=2 * slippage_pts_lado, swap_pts=swap,
                spread_usd=spread_pts * vp * lotes, slippage_usd=2 * slippage_pts_lado * vp * lotes,
                swap_usd=swap * vp * lotes, comision_usd=com,
                total_usd=pts * vp * lotes + com, total_pts=pts,    # puntos POR lote (sin comision)
                slippage_modelado=slippage_pts_lado > 0, valor_punto_lote=vp, nota=c.nota)


def comparar_brokers_cfd(inst: str, lotes: float = 1.0, **kw) -> dict:
    """Costo ida y vuelta por broker (None donde el usuario no dio spread). Para comparar IC Markets / Pepperstone / XM."""
    out = {}
    for b in BROKERS_CFD:
        try:
            out[b] = costo_trade_cfd(inst, lotes=lotes, broker=b, **kw)["total_usd"]
        except ValueError:
            out[b] = None
    return out


def estado_verificacion_cfd(tabla=None) -> dict:
    tabla = TABLA_CFD if tabla is None else tabla
    return dict(total=len(tabla), verificados=0, sin_verificar=sorted(f"{c.inst}/{c.broker}" for c in tabla.values()),
                sin_spread=sorted(f"{c.inst}/{c.broker}" for c in tabla.values() if not c.tiene_spread))
