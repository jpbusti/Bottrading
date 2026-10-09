"""Motor US100 v1: reglas de docs/PREREGISTRO_US100_V1.md (H1 ORB, H2 VWAP, H3 PDH/PDL, H4 area de valor).

Datos: velas 1m del CFD USTEC (IC Markets demo). Hora servidor = hora ET + 7 -> se trabaja en hora de pared de NY.
Indices por dia: idx 0 = 09:30 ET ... idx 389 = 15:59 ET. Ventana de trading: senal al cierre de idx s (15..119),
entrada en la apertura de idx s+1 (<= 120 = 11:30), salida forzada al cierre de idx 149 (11:59).
Las reglas son las del pre-registro; los multiplicadores `thr`, `tpm`, `slm` existen SOLO para la rejilla de robustez.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from validacion.cost_model import costo_trade_cfd  # noqa: E402

CSV = Path(__file__).resolve().parents[2] / "data" / "raw" / "us100" / "USTEC_ICMarkets_demo_1m.csv"
DESDE = "2018-01-01"
N_RTH, FIN_VENTANA, MAX_ENTRADA, S_MIN = 390, 149, 120, 15      # S_MIN=15 -> 09:45
OFFSET_SERVIDOR_H = 7
BIN = 2.5
COSTO_BASE = costo_trade_cfd("US100", slippage_pts_lado=0.25)["total_pts"]       # 1.5 + 0.5 = 2.0
COSTO_ESTRES = costo_trade_cfd("US100", slippage_pts_lado=0.75)["total_pts"]     # 1.5 + 1.5 = 3.0


@dataclass
class Dia:
    fecha: object
    o: np.ndarray; h: np.ndarray; l: np.ndarray; c: np.ndarray; v: np.ndarray   # largo 390, NaN si falta
    hi: float = np.nan; lo: float = np.nan; cierre: float = np.nan; rango: float = np.nan
    poc: float = np.nan; vah: float = np.nan; val: float = np.nan
    vwap: np.ndarray | None = None
    atr: float = np.nan
    verano: bool = True


def cargar_dias(ruta=CSV, desde=DESDE) -> list[Dia]:
    d = pd.read_csv(ruta, parse_dates=["time_server"])
    d = d[d.time_server >= desde]
    et = d.time_server - pd.Timedelta(hours=OFFSET_SERVIDOR_H)
    m = et.dt.hour * 60 + et.dt.minute - 570
    ok = (m >= 0) & (m < N_RTH)
    d, et, m = d[ok], et[ok], m[ok].astype(int).values
    fechas = et.dt.date.values
    cols = {k: d[k].values.astype(float) for k in ("open", "high", "low", "close", "tick_volume")}
    dias = []
    ini = np.r_[0, np.flatnonzero(fechas[1:] != fechas[:-1]) + 1]
    fin = np.r_[ini[1:], len(fechas)]
    for a, b in zip(ini, fin):
        arr = {k: np.full(N_RTH, np.nan) for k in cols}
        for k in cols:
            arr[k][m[a:b]] = cols[k][a:b]
        x = Dia(fechas[a], arr["open"], arr["high"], arr["low"], arr["close"], arr["tick_volume"])
        x.verano = bool(pd.Timestamp(f"{fechas[a]} 12:00").tz_localize("America/New_York").dst() != pd.Timedelta(0))
        if np.isfinite(x.c).sum() >= 350 and np.isfinite(x.c[:150]).sum() >= 150:
            x.hi, x.lo, x.rango = np.nanmax(x.h), np.nanmin(x.l), np.nanmax(x.h) - np.nanmin(x.l)
            x.cierre = x.c[~np.isnan(x.c)][-1]
            x.vwap = _vwap(x)
            x.poc, x.vah, x.val = _perfil(x)
            dias.append(x)
    for i, x in enumerate(dias):
        x.atr = np.mean([y.rango for y in dias[i - 14:i]]) if i >= 14 else np.nan
    return dias


def _vwap(x: Dia) -> np.ndarray:
    tp = (x.h + x.l + x.c) / 3
    v = np.where(np.isnan(x.v), 0.0, x.v)
    pv = np.where(np.isnan(tp), 0.0, tp) * v
    cv = np.cumsum(v)
    return np.where(cv > 0, np.cumsum(pv) / np.where(cv > 0, cv, 1), np.nan)


def _perfil(x: Dia):
    """POC y area de valor 70% (expansion un contenedor a la vez hacia el lado con mas volumen), contenedor 2.5 pts."""
    ok = ~np.isnan(x.h) & ~np.isnan(x.v)
    h, l, v = x.h[ok], x.l[ok], x.v[ok]
    b0 = int(np.floor(l.min() / BIN))
    nb = int(np.floor(h.max() / BIN)) - b0 + 1
    bl, bh = np.floor(l / BIN).astype(int) - b0, np.floor(h / BIN).astype(int) - b0
    share = v / (bh - bl + 1)
    dif = np.zeros(nb + 1)
    np.add.at(dif, bl, share)
    np.add.at(dif, bh + 1, -share)
    p = np.cumsum(dif)[:nb]
    k = int(np.argmax(p))
    lo_i = hi_i = k
    tot, acum = p.sum(), p[k]
    while acum < 0.7 * tot and (lo_i > 0 or hi_i < nb - 1):
        up = p[hi_i + 1] if hi_i < nb - 1 else -1
        dn = p[lo_i - 1] if lo_i > 0 else -1
        if up >= dn:
            hi_i += 1; acum += p[hi_i]
        else:
            lo_i -= 1; acum += p[lo_i]
    f = lambda i: (i + b0) * BIN + BIN / 2          # noqa: E731
    return f(k), (hi_i + b0 + 1) * BIN, (lo_i + b0) * BIN


# ---------------------------------------------------------------- simulacion
def simular(x: Dia, s: int, d: int, sl_dist: float, tp_dist: float, costo: float = COSTO_BASE):
    """Entrada en apertura de idx s+1. Devuelve (R neta, pnl_pts, motivo) o None si no hay fill valido."""
    e = s + 1
    if e > MAX_ENTRADA or np.isnan(x.o[e]) or sl_dist <= 0 or tp_dist <= 0:
        return None
    entry = x.o[e]
    sl, tp = entry - d * sl_dist, entry + d * tp_dist
    hh, ll, cc = x.h[e:FIN_VENTANA + 1], x.l[e:FIN_VENTANA + 1], x.c[e:FIN_VENTANA + 1]
    if d == 1:
        ps, pt = ll <= sl, hh >= tp
    else:
        ps, pt = hh >= sl, ll <= tp
    i_sl = int(np.argmax(ps)) if ps.any() else 10 ** 6
    i_tp = int(np.argmax(pt)) if pt.any() else 10 ** 6
    if i_sl <= i_tp and i_sl < 10 ** 6:
        pnl, mot = -sl_dist, "SL"
    elif i_tp < 10 ** 6:
        pnl, mot = tp_dist, "TP"
    else:
        ok = ~np.isnan(cc)
        if not ok.any():
            return None
        pnl, mot = d * (cc[ok][-1] - entry), "T"
    return (pnl - costo) / sl_dist, pnl, mot, entry


# ---------------------------------------------------------------- generadores de senal
def _primer(cond: np.ndarray, desde: int, hasta: int = 119):
    c = cond[desde:hasta + 1]
    return desde + int(np.argmax(c)) if c.any() else None


def senal(hip: str, x: Dia, niv: Dia, thr: float = 1.0, tpm: float = 1.5, slm: float = 0.20):
    """x = dia operado; niv = dia del que salen los niveles (D-1 en el caso base; D-N en el placebo de nivel).
    Devuelve dict(s, d, sl_fn, tp_fn) o None. sl_fn/tp_fn(entry) -> distancia en puntos (>0)."""
    A, c = x.atr, x.c
    if np.isnan(A):
        return None
    if hip == "H1":
        orh, orl = np.nanmax(niv.h[:15]), np.nanmin(niv.l[:15])
        w = orh - orl
        if not (0.10 * thr * A <= w <= 0.60 * thr * A):
            return None
        s = _primer((c > orh) | (c < orl), S_MIN)
        if s is None:
            return None
        d = 1 if c[s] > orh else -1
        # SL = lado opuesto del OR (fijo en precio); distancia depende de la entrada
        return dict(s=s, d=d, sl=lambda e: abs(e - (orl if d == 1 else orh)), tp=lambda e: tpm * abs(e - (orl if d == 1 else orh)))
    if hip == "H2":
        return _senal_h2(x, niv, thr, slm)
    if hip in ("H3", "H4"):
        off, cap = 0.15 * thr * A, 0.50 * thr * A
        if hip == "H3":
            s = _primer((c > niv.hi) | (c < niv.lo), S_MIN)
            if s is None:
                return None
            d = 1 if c[s] > niv.hi else -1
            nivel = niv.hi if d == 1 else niv.lo
            sl = lambda e: d * (e - nivel) + off                       # noqa: E731
            return dict(s=s, d=d, sl=sl, tp=lambda e: tpm * sl(e), cap=cap)
        prev = np.r_[np.nan, c[:-1]]
        short = (x.h >= niv.vah) & (c < niv.vah) & (prev < niv.vah)
        long_ = (x.l <= niv.val) & (c > niv.val) & (prev > niv.val)
        s = _primer(short | long_, S_MIN)
        if s is None:
            return None
        d = -1 if short[s] else 1
        nivel = niv.vah if d == -1 else niv.val
        sl = lambda e: d * (e - nivel) + off                           # noqa: E731
        return dict(s=s, d=d, sl=sl, tp=lambda e: d * (niv.poc - e), cap=cap, min_tp=0.15 * thr * A)
    raise ValueError(hip)


def correr(hip: str, dias: list[Dia], lag: int = 1, thr: float = 1.0, tpm: float = 1.5, slm: float = 0.20,
           costo: float = COSTO_BASE, invertir: bool = False, desde=None) -> pd.DataFrame:
    """Backtest de una hipotesis. lag = indice de dia previo del que salen los niveles (1 = D-1)."""
    filas = []
    for i, x in enumerate(dias):
        if i < 15 or i - lag < 0 or (i - 1) < 0:
            continue
        if desde is not None and x.fecha < desde:
            continue
        if hip == "H2":
            niv = x if lag == 1 else dias[i - lag]          # base: VWAP del propio dia D; placebo: curva de D-N
        else:
            niv = dias[i - lag]
        sg = senal(hip, x, niv, thr, tpm, slm)
        if sg is None:
            continue
        e = sg["s"] + 1
        if e > MAX_ENTRADA or np.isnan(x.o[e]):
            continue
        entry = x.o[e]
        sl_d, tp_d = sg["sl"](entry), sg["tp"](entry)
        if "cap" in sg and sl_d > sg["cap"]:
            continue
        if "min_tp" in sg and tp_d < sg["min_tp"]:
            continue
        if sl_d <= 0 or tp_d <= 0:
            continue
        d = -sg["d"] if invertir else sg["d"]
        r = simular(x, sg["s"], d, sl_d, tp_d, costo)
        if r is None:
            continue
        filas.append(dict(fecha=x.fecha, anio=x.fecha.year, verano=x.verano, s=sg["s"], d=d, sl_dist=sl_d, tp_dist=tp_d,
                          R=r[0], pnl=r[1], motivo=r[2], entry=r[3]))
    return pd.DataFrame(filas)


def _senal_h2(x: Dia, niv: Dia, thr: float, slm: float):
    A, c = x.atr, x.c
    if np.isnan(A):
        return None
    dev = c - niv.vwap
    s = _primer(np.abs(np.nan_to_num(dev)) >= 0.20 * thr * A, 30)
    if s is None:
        return None
    d = -1 if dev[s] > 0 else 1
    vw = niv.vwap[s]
    return dict(s=s, d=d, sl=lambda e: slm * A, tp=lambda e: d * (vw - e))


def placebo_timing_r(tr: pd.DataFrame, dias_por_fecha: dict, seed: int, costo: float = COSTO_BASE) -> np.ndarray:
    """Mismos dias y distancias SL/TP que los trades reales; minuto de entrada y direccion al azar."""
    rng = np.random.default_rng(seed)
    out = []
    for f, sl_d, tp_d in zip(tr.fecha.values, tr.sl_dist.values, tr.tp_dist.values):
        x = dias_por_fecha[f]
        s = int(rng.integers(S_MIN, 120))
        d = 1 if rng.random() < 0.5 else -1
        r = simular(x, s, d, sl_d, tp_d, costo)
        if r is not None:
            out.append(r[0])
    return np.array(out)
