"""
Motor Liquidity Sweep Reversal v1 (LSR v1) - reglas en claude/PREREGISTRO_LSR_V1.md.
- Contrato operado del dia D = contrato dominante (mayor volumen RTH) de D-1; PDH/PDL/cierre de ESE contrato en D-1.
- Velas 5m desde 1m; sin actualizar niveles intradia; un trade por dia y bloque.
- Bloque A: barrido desde 09:30, entrada (cierre de vela de reclaim) en 09:45-12:00 o 14:00-15:30 ET, salida 15:59.
- Bloque B: premercado 04:00-09:30, volumen de la vela de barrido > 1.5x media 20 velas previas, salida 09:29.
- SL/TP: k*ATR14, m*ATR14 (ATR diario RTH hasta D-1), o estructural. SL antes que TP si ambos en la misma vela 1m.
"""
from __future__ import annotations
import datetime as dt
import logging
from dataclasses import dataclass
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from validacion import cost_model as _cm, pf_inference as _pi, walkforward as _wf   # noqa: E402

log = logging.getLogger("lsr")
TICK = 0.25
MULT = {"NQ": 20.0, "ES": 50.0}
KS, MS = (0.8, 1.0, 1.2), (1.5, 1.75, 2.0)
REF = (0.179, 0.247)
MIN_BARRAS_RTH = 350
FOMC = """2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-04 2019-10-30 2019-12-11
2020-01-29 2020-03-02 2020-03-03 2020-03-16 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16""".split()
FOMC = {dt.date.fromisoformat(s) for s in FOMC}


def costo_pts(inst: str, anio: int) -> float:
    """Costo ida y vuelta en puntos: slippage 1 tick/lado + spread + comision. [VERIFICAR] -> validacion/cost_model.py"""
    return _cm.costo_pts(inst, anio)


def es_opex(d: dt.date) -> bool:
    return d.weekday() == 4 and 15 <= d.day <= 21


@dataclass
class Dia:
    fecha: dt.date
    sym: str
    t: np.ndarray; o: np.ndarray; h: np.ndarray; l: np.ndarray; c: np.ndarray; v: np.ndarray
    b5: dict  # arrays de velas 5m: s,e,o,h,l,c,v,i1


def _barras5(t, o, h, l, c, v) -> dict:
    b = t // 5
    cut = np.r_[0, np.where(np.diff(b) != 0)[0] + 1]
    end = np.r_[cut[1:], len(t)]
    return dict(s=(b[cut] * 5), e=(b[cut] * 5 + 5), o=o[cut], c=c[end - 1], i1=end,
                h=np.maximum.reduceat(h, cut), l=np.minimum.reduceat(l, cut), v=np.add.reduceat(v, cut))


class Mercado:
    def __init__(self, df: pd.DataFrame, nombre: str):
        self.nombre = nombre
        self.g: dict = {}
        for (f, s), g in df.groupby(["fecha", "symbol"], observed=True):
            g = g.sort_values("Datetime")
            t = (g["Datetime"].dt.hour * 60 + g["Datetime"].dt.minute).values.astype(int)
            a = [g[x].values.astype(float) for x in ["Open", "High", "Low", "Close", "Volume"]]
            self.g[(f, s)] = Dia(f, s, t, *a, _barras5(t, *a))
        self.fechas = sorted({f for f, _ in self.g})
        self.rth = {}
        for (f, s), d in self.g.items():
            m = d.t >= 570
            if m.sum() >= 30:
                self.rth[(f, s)] = (d.h[m].max(), d.l[m].min(), d.c[m][-1], d.v[m].sum(), int(m.sum()))
        self.dom = {}
        for f in self.fechas:
            c = [(self.rth[(f, s)][3], s) for (ff, s) in self.rth if ff == f] if False else None
        by = {}
        for (f, s), r in self.rth.items():
            by.setdefault(f, []).append((r[3], s))
        for f, lst in by.items():
            self.dom[f] = max(lst)[1]
        self.fechas = [f for f in self.fechas if f in self.dom]
        self._atr()
        log.info("%s: %d dias, %d contratos-dia", nombre, len(self.fechas), len(self.g))

    def _atr(self):
        tr = []
        for i, f in enumerate(self.fechas):
            s = self.dom[f]
            H, L, C, _, _ = self.rth[(f, s)]
            pc = None
            if i > 0:
                r = self.rth.get((self.fechas[i - 1], s))
                pc = r[2] if r else None
            tr.append(max(H - L, abs(H - pc), abs(L - pc)) if pc is not None else H - L)
        self.tr = pd.Series(tr, index=self.fechas)
        self.atr = self.tr.rolling(14).mean()   # ATR hasta el cierre de cada fecha

    # --------------------------------------------------------------
    def dias(self, lag: int = 1):
        """Genera (D, ctx) con la informacion disponible al inicio de D. lag=2 -> placebo (niveles de D-2)."""
        F = self.fechas
        for i in range(max(16, lag + 1), len(F)):
            D, P = F[i], F[i - 1]
            if (D - P).days > 5:
                continue
            C = self.dom[P]
            if (D, C) not in self.g or (P, C) not in self.rth:
                continue
            L = F[i - lag]
            if (L, C) not in self.rth:
                continue
            atr = self.atr.iloc[i - 1]
            hist = self.atr.iloc[:i - 1].dropna()
            if np.isnan(atr) or len(hist) < 60:
                continue
            pct = float((hist < atr).mean())
            H_, L_, C_, _, _ = self.rth[(L, C)]
            yield D, dict(sym=C, PDH=H_, PDL=L_, PDC=C_, atr=float(atr), pct=pct,
                          roll=(self.dom.get(F[i - 2]) != C) if i >= 2 else False,
                          nrth=self.rth[(D, C)][4], dia=self.g[(D, C)], prev=self.g.get((P, C)))


def _signals(ctx, bloque: str, N: int, volmult: float = 1.5):
    """Senales de barrido+reclaim sobre velas 5m. Devuelve lista (dir, lvl, extremo, j, fin_min)."""
    b = ctx["dia"].b5
    s, e, h, l, c, v, o = b["s"], b["e"], b["h"], b["l"], b["c"], b["v"], b["o"]
    n = len(s)
    if bloque == "A":
        ini = int(np.searchsorted(s, 570)); fin_ok = lambda ee: ee <= 16 * 60
    else:
        ini = 0; fin_ok = lambda ee: ee <= 570
    if bloque == "A" and ini == 0 and ctx["prev"] is not None:
        pass
    PDH, PDL = ctx["PDH"], ctx["PDL"]
    out = []
    k = ini
    while k < n:
        if bloque == "B" and s[k] >= 570:
            break
        if not fin_ok(e[k]):
            break
        pc = c[k - 1] if k > 0 else o[k]   # sin premercado: se usa la apertura
        if pc is None:
            k += 1; continue
        ok_vol = True
        if bloque == "B":
            ok_vol = k >= 10 and v[k] > volmult * v[max(0, k - 20):k].mean()
        hit = None
        if l[k] < PDL and pc >= PDL:
            hit = 1
        elif h[k] > PDH and pc <= PDH:
            hit = -1
        if hit is None or not ok_vol:
            k += 1; continue
        lvl = PDL if hit == 1 else PDH
        ext = l[k] if hit == 1 else h[k]
        done = False
        for j in range(k, min(k + N, n)):
            if not fin_ok(e[j]) or (bloque == "B" and s[j] >= 570):
                break
            ext = min(ext, l[j]) if hit == 1 else max(ext, h[j])
            if (hit == 1 and c[j] > lvl) or (hit == -1 and c[j] < lvl):
                out.append((hit, lvl, ext, j, int(e[j])))
                k = j + 1; done = True
                break
        if not done:
            k += 1
    return out


def _en_ventana(fin: int, ventanas) -> bool:
    return any(a <= fin <= z for a, z in ventanas)


VENT_A = ((9 * 60 + 45, 12 * 60), (14 * 60, 15 * 60 + 30))


def simular(d: Dia, sig, modo_entrada: str, sl: float, tp: float, fin_sesion: int):
    """Devuelve (pnl_pts, motivo, salida_min) o None."""
    dr, lvl, ext, j, fin = sig
    b = d.b5
    i1 = int(b["i1"][j])
    ult = int(np.searchsorted(d.t, fin_sesion, side="right")) - 1
    if i1 > ult or i1 >= len(d.t):
        return None
    ent = b["c"][j] if modo_entrada == "close" else d.o[i1]
    sl_px, tp_px = ent - dr * sl, ent + dr * tp
    h, l = d.h[i1:ult + 1], d.l[i1:ult + 1]
    if dr == 1:
        hs, ht = l <= sl_px, h >= tp_px
    else:
        hs, ht = h >= sl_px, l <= tp_px
    a = np.argmax(hs) if hs.any() else None
    z = np.argmax(ht) if ht.any() else None
    if a is not None and (z is None or a <= z):
        return dr * (sl_px - ent), "SL", int(d.t[i1 + a])
    if z is not None:
        return dr * (tp_px - ent), "TP", int(d.t[i1 + z])
    return dr * (d.c[ult] - ent), "EOD", int(d.t[ult])


def generar(M: Mercado, bloque="A", N=4, modo_entrada="close", ventanas=VENT_A, estructural=False,
            lag=1, filtros=True, extra_ks=(REF,), volmult=1.5, grid=True,
            invertir=False, timing_rng=None) -> pd.DataFrame:
    """Un registro por (trade, combo). combo=(k,m) o 'EST'.
    Placebos: lag=N (niveles de D-N); invertir=True (direccion opuesta, re-simulada);
    timing_rng=np.random.Generator (cada senal se entrena en una vela 5m aleatoria de la ventana, misma gestion)."""
    rows = []
    fin_sesion = 959 if bloque == "A" else 569
    combos = [(k, m) for k in KS for m in MS] if grid else []
    combos += list(extra_ks)
    for D, x in M.dias(lag):
        if filtros:
            if x["pct"] < 0.10 or x["roll"] or D in FOMC or es_opex(D) or x["nrth"] < MIN_BARRAS_RTH:
                continue
        sigs = [s for s in _signals(x, bloque, N, volmult)
                if (bloque == "B" or _en_ventana(s[4], ventanas))]
        if not sigs:
            continue
        d, atr = x["dia"], x["atr"]
        if timing_rng is not None:
            e5 = d.b5["e"]
            cand = [jj for jj in range(len(e5)) if (bloque == "B" or _en_ventana(int(e5[jj]), ventanas))
                    and (bloque == "B" and int(e5[jj]) <= 570 or bloque == "A")]
            if not cand:
                continue
            sigs = [(s[0], s[1], s[2], int(j2), int(e5[j2])) for s in sigs for j2 in [timing_rng.choice(cand)]]
        if invertir:
            sigs = [(-s[0],) + tuple(s[1:]) for s in sigs]
        for sig in sigs:
            dr, lvl, ext, j, fin = sig
            ent_ref = d.b5["c"][j]
            if estructural:
                sl = max(abs(ent_ref - (ext - dr * TICK)), 0.1 * atr)
                tp = (x["PDH"] - ent_ref) if dr == 1 else (ent_ref - x["PDL"])
                res_list = [("EST", sl, tp)] if tp > 0 else []
            else:
                res_list = [((k, m), k * atr, m * atr) for k, m in combos]
            trade_any = False
            for cb, sl, tp in res_list:
                r = simular(d, sig, modo_entrada, sl, tp, fin_sesion)
                if r is None:
                    continue
                trade_any = True
                rows.append(dict(fecha=D, anio=D.year, bloque=bloque, dir=dr, fin=fin, combo=cb, sl=sl, tp=tp,
                                 atr=atr, pnl=r[0], motivo=r[1], salida=r[2], sym=x["sym"]))
            if trade_any:
                break   # un trade por dia y bloque
    df = pd.DataFrame(rows)
    if len(df):
        df["costo"] = [costo_pts(M.nombre, a) for a in df.anio]
    return df


# ------------------------------------------------------------------ metricas
def Rnet(df: pd.DataFrame, f: float = 1.0) -> np.ndarray:
    return ((df.pnl - f * df.costo) / df.sl).values


pf = _pi.pf
maxdd = _pi.maxdd


def boot_pf(r: np.ndarray, n=5000, seed=7):
    b = _pi.bootstrap_iid(r, n, seed)
    return b["pf_lo"], b["pf_med"], b["pf_hi"]


def resumen(df: pd.DataFrame, mult: float, f: float = 1.0, riesgo: float = 0.005) -> dict:
    if len(df) == 0:
        return dict(n=0)
    r = Rnet(df, f)
    rg = ((df.pnl) / df.sl).values
    lo, med, hi = boot_pf(r)
    dd = maxdd(r)
    usd = (df.pnl - f * df.costo).values * mult
    pu = usd[usd > 0].sum() / max(-usd[usd < 0].sum(), 1e-9)
    return dict(n=len(df), PF_bruto=pf(rg), PF_neto=pf(r), PF_lo90=lo, PF_hi90=hi, PF_usd=float(pu),
                expR=float(r.mean()), win=float((r > 0).mean() * 100), DD_R=dd, DD_pct=dd * riesgo * 100,
                DD_pct_1=dd * 0.01 * 100)


mc_dd = _pi.mc_dd_iid


def walk_forward(df: pd.DataFrame, anio_ini=2019, min_tr=30):
    """Entrena con anios < Y (expansivo), elige combo con mayor PF neto (>=min_tr trades), prueba en Y."""
    return _wf.walk_forward(df, Rnet, combo_ref=REF, combo_defecto=(1.0, 1.75), anio_ini=anio_ini, min_tr=min_tr)
