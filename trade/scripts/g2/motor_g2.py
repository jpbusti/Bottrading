"""
Motor de validacion G2 (regla congelada: barrido + retest + VWAP, SL/TP fijos normalizados).

- Niveles, cierre previo y perfil se calculan con el MISMO contrato que se opera.
- Escala del dia s_D (solo informacion hasta el cierre de D-1):
    metodo "ATR": s = ATR14(D-1) / ATR_CAL
    metodo "PCT": s = Close(D-1) / P_CAL
    metodo "FIJO": s = 1  (puntos fijos, sin normalizar)
  Todos los parametros en puntos (SL, TP, barrido, tolerancia de retest, bin) se multiplican por s_D.
- Logica de senales, perfil y simulacion copiada de scripts/marco_subastas_stop_amplio.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from validacion import pf_inference as _pi   # noqa: E402

log = logging.getLogger("g2")
NY = "America/New_York"

# Parametros congelados (en puntos NQ del periodo de seleccion)
BIN0, VA_PCT = 2.5, 0.70
SWEEP0, RETEST0 = 2.0, 1.0
RECLAIM_BARS, RETEST_FILL_1M, HORA_MAX = 6, 60, 15 * 60
SL0, TP0 = 80.0, 110.0
P_CAL, ATR_CAL = 27205.8, 445.9      # calibracion 2025-10-07 -> 2026-10-06 (254 sesiones)
MIN_BARRAS = 200


@dataclass
class Dia:
    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    avwap: np.ndarray
    barras: list


def _dia(g: pd.DataFrame) -> Dia:
    t = (g["Datetime"].dt.hour * 60 + g["Datetime"].dt.minute).values
    o, h, l, c, v = (g[x].values.astype(float) for x in ["Open", "High", "Low", "Close", "Volume"])
    tp = (h + l + c) / 3
    avwap = np.cumsum(tp * v) / np.maximum(np.cumsum(v), 1)
    k5 = (t - 570) // 5
    barras = []
    for k in np.unique(k5):
        idx = np.where(k5 == k)[0]
        i0, i1 = idx[0], idx[-1] + 1
        barras.append((int(t[i0]) + 5, o[i0], h[i0:i1].max(), l[i0:i1].min(), c[i1 - 1], i1))
    return Dia(t, o, h, l, c, v, avwap, barras)


def perfil(d: Dia, bin_: float) -> dict:
    tp = (d.h + d.l + d.c) / 3
    b = np.round(tp / bin_) * bin_
    s = pd.Series(d.v).groupby(b).sum().sort_index()
    p, vol = s.index.values, s.values
    ip = int(np.argmax(vol))
    lo = hi = ip
    acc, tot = vol[ip], vol.sum()
    while acc < VA_PCT * tot and (lo > 0 or hi < len(vol) - 1):
        up = vol[hi + 1:hi + 3].sum() if hi < len(vol) - 1 else -1
        dn = vol[max(lo - 2, 0):lo].sum() if lo > 0 else -1
        if up >= dn:
            add = vol[hi + 1:hi + 3]
            hi += len(add)
        else:
            add = vol[max(lo - 2, 0):lo]
            lo -= len(add)
        acc += add.sum()
    return dict(POC=p[ip], VAH=p[hi], VAL=p[lo])


def senales_A(d: Dia, niveles: dict, prev_close: float, sweep: float) -> list:
    """Setup A (barrido + recuperacion). Devuelve (dir, nivel_px, extremo, i1, close5, nombre)."""
    out = []
    sw_up, sw_dn = {}, {}
    pc = prev_close
    for k, (tfin, o, h, l, c, i1) in enumerate(d.barras):
        if tfin > HORA_MAX:
            break
        for nm, lv in niveles.items():
            if nm in sw_up:
                k0, ext = sw_up[nm]
                ext = max(ext, h)
                sw_up[nm] = (k0, ext)
                if c < lv:
                    out.append((-1, lv, ext, i1, c, nm))
                    del sw_up[nm]
                elif k - k0 >= RECLAIM_BARS:
                    del sw_up[nm]
            elif h > lv + sweep and pc < lv:
                if c < lv:
                    out.append((-1, lv, h, i1, c, nm))
                else:
                    sw_up[nm] = (k, h)
            if nm in sw_dn:
                k0, ext = sw_dn[nm]
                ext = min(ext, l)
                sw_dn[nm] = (k0, ext)
                if c > lv:
                    out.append((1, lv, ext, i1, c, nm))
                    del sw_dn[nm]
                elif k - k0 >= RECLAIM_BARS:
                    del sw_dn[nm]
            elif l < lv - sweep and pc > lv:
                if c > lv:
                    out.append((1, lv, l, i1, c, nm))
                else:
                    sw_dn[nm] = (k, l)
        pc = c
    return out


def simular(d: Dia, sig: tuple, sl: float, tp: float, through: float):
    """Entrada limit en el nivel (retest) y salida con SL/TP fijos o cierre. Devuelve dict o None."""
    dr, lv, ext, i1, c5, nm = sig
    n = len(d.c)
    ent, j0 = None, None
    for j in range(i1, min(i1 + RETEST_FILL_1M, n)):
        if (dr == -1 and d.h[j] >= lv + through) or (dr == 1 and d.l[j] <= lv - through):
            ent, j0 = lv, j
            break
    if ent is None:
        return None
    stop, tgt = ent - dr * sl, ent + dr * tp
    sal, motivo = d.c[-1], "cierre"
    for j in range(j0, n):
        if dr == 1:
            if d.l[j] <= stop:
                sal, motivo = stop, "SL"; break
            if d.h[j] >= tgt:
                sal, motivo = tgt, "TP"; break
        else:
            if d.h[j] >= stop:
                sal, motivo = stop, "SL"; break
            if d.l[j] <= tgt:
                sal, motivo = tgt, "TP"; break
    return dict(dir=dr, nivel=nm, ent=ent, sal=sal, motivo=motivo, gross=(sal - ent) * dr,
                t_ent=int(d.t[j0]))


class Mercado:
    """Carga velas por (fecha, contrato) y expone la ejecucion del backtest."""

    def __init__(self, df: pd.DataFrame, nombre: str):
        self.nombre = nombre
        self.dias: dict[tuple, Dia] = {}
        self.vol: dict = {}
        for (f, s), g in df.groupby(["fecha", "symbol"], sort=True):
            if len(g) >= MIN_BARRAS:
                self.dias[(f, s)] = _dia(g.sort_values("Datetime"))
                self.vol.setdefault(f, {})[s] = float(g["Volume"].sum())
        self.fechas = sorted(self.vol)
        self.dom = {f: max(self.vol[f], key=self.vol[f].get) for f in self.fechas}
        self._cache_perfil: dict = {}
        self._atr = self._calc_atr()
        self.rolls = self._calc_rolls()
        log.info("%s: %d dias validos (%s -> %s), %d rolls", nombre, len(self.fechas),
                 self.fechas[0], self.fechas[-1], len(self.rolls))

    def _calc_rolls(self) -> list:
        """Fecha D es 'roll' si el contrato operado en D (dominante de D-1) != el de D-1."""
        out = []
        for i in range(2, len(self.fechas)):
            if self.dom[self.fechas[i - 1]] != self.dom[self.fechas[i - 2]]:
                out.append(self.fechas[i])
        return out

    def _calc_atr(self) -> pd.Series:
        tr = {}
        for i, f in enumerate(self.fechas):
            s = self.dom[f]
            d = self.dias[(f, s)]
            h, l = d.h.max(), d.l.min()
            r = h - l
            if i > 0:
                prev = self.dias.get((self.fechas[i - 1], s))
                if prev is not None:
                    pc = prev.c[-1]
                    r = max(r, abs(h - pc), abs(l - pc))
            tr[f] = r
        return pd.Series(tr).rolling(14).mean()

    def _niveles(self, f: str, s: str, bin_: float) -> dict:
        k = (f, s, round(bin_, 5))
        if k not in self._cache_perfil:
            d = self.dias[(f, s)]
            n = perfil(d, bin_)
            n["PDH"], n["PDL"] = d.h.max(), d.l.min()
            self._cache_perfil[k] = n
        return dict(self._cache_perfil[k])

    def correr(self, metodo: str, lag: int = 1, through: float = 0.0, modo_filtro: str = "pre",
               usar_hora: bool = True, sin_poc: bool = True, warm: int = 15,
               desde=None, hasta=None) -> pd.DataFrame:
        rolls = set(self.rolls)
        idx_roll = [i for i, f in enumerate(self.fechas) if f in rolls]
        trades = []
        for di, f in enumerate(self.fechas):
            if di < max(lag, warm):
                continue
            if (desde and f < desde) or (hasta and f > hasta):
                continue
            fprev, fp = self.fechas[di - 1], self.fechas[di - lag]
            s = self.dom[fprev]
            if (f, s) not in self.dias or (fp, s) not in self.dias or (fprev, s) not in self.dias:
                continue
            prev_close = self.dias[(fprev, s)].c[-1]
            if metodo == "ATR":
                atr = self._atr.get(fprev)
                if atr is None or np.isnan(atr):
                    continue
                esc = atr / ATR_CAL
            elif metodo == "PCT":
                esc = prev_close / P_CAL
            else:
                esc = 1.0
            niveles = self._niveles(fp, s, BIN0 * esc)
            d = self.dias[(f, s)]
            cands = senales_A(d, niveles, prev_close, SWEEP0 * esc)
            sl, tp = SL0 * esc, TP0 * esc
            for sig in cands:
                dr, lv, ext, i1, c5, nm = sig
                av = d.avwap[i1 - 1]
                if (dr == 1 and c5 <= av) or (dr == -1 and c5 >= av):
                    continue
                if modo_filtro == "pre" and sin_poc and nm == "POC":
                    continue
                r = simular(d, sig, sl, tp, through * esc)
                if r is None:
                    continue
                if modo_filtro == "pre" and usar_hora and r["t_ent"] >= 630:
                    continue
                if modo_filtro == "post":
                    if (usar_hora and r["t_ent"] >= 630) or (sin_poc and nm == "POC"):
                        break
                r.update(fecha=f, sym=s, sl=sl, tp=tp, esc=esc)
                # dias desde el ultimo roll (0 = el propio dia del roll)
                prev_rolls = [j for j in idx_roll if j <= di]
                r["dsr"] = di - prev_rolls[-1] if prev_rolls else 999
                trades.append(r)
                break
        return pd.DataFrame(trades)


# ----------------------------------- estadistica -----------------------------------
def pf(x: np.ndarray) -> float:
    return _pi.pf(x, sin_perdidas=99.0)


def r_mult(t: pd.DataFrame, costo: float) -> np.ndarray:
    return ((t["gross"] - costo) / t["sl"]).values


def resumen(t: pd.DataFrame, costo: float, n_boot: int = 5000, seed: int = 42) -> dict:
    if len(t) == 0:
        return dict(n=0)
    R = r_mult(t, costo)
    b = _pi.bootstrap_iid(R, n_boot, seed, sin_perdidas=99.0)
    return dict(n=len(R), win=(R > 0).mean() * 100, PF=pf(R), expR=R.mean(),
                exp_lo=b["exp_lo"], exp_hi=b["exp_hi"], pf_lo=b["pf_lo"], pf_hi=b["pf_hi"],
                pts_trade=((t["gross"] - costo).mean()))


def por_anio(t: pd.DataFrame, costo: float, min_n: int = 30) -> pd.DataFrame:
    if len(t) == 0:
        return pd.DataFrame()
    R = pd.Series(r_mult(t, costo), index=pd.to_datetime(t["fecha"]).dt.year.values)
    rows = []
    for y, g in R.groupby(level=0):
        rows.append(dict(anio=y, n=len(g), PF=pf(g.values), expR=g.mean()))
    return pd.DataFrame(rows)


def monte_carlo_dd(R: np.ndarray, bloque: int = 20, n_paths: int = 5000, seed: int = 7) -> dict:
    return _pi.monte_carlo_dd_bloques(R, bloque, n_paths, seed)
