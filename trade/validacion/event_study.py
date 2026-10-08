"""Fase 0: estudio de eventos. Retornos forward tras un evento vs un baseline (mismo dia, misma hora, sin evento).

Entrada: velas 1m de una sola sesion/contrato por dia (columnas Datetime tz ET, Close) y la lista de eventos
(Datetime del instante de la senal). Retornos en puntos y normalizados por ATR diario si se pasa `atr`.
NO define hipotesis: solo mide. Aun sin usar en ningun estudio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONTES = {"30m": 30, "1h": 60, "2h": 120, "cierre": None}


def _retorno_fwd(df_dia: pd.DataFrame, t0, minutos, direccion: int = 1):
    """Retorno (pts) de cierre en t0 a cierre en t0+minutos (o a la ultima vela del dia si minutos=None)."""
    g = df_dia.set_index("Datetime")["Close"]
    if t0 not in g.index:
        return np.nan
    p0 = g.loc[t0]
    if minutos is None:
        p1 = g.iloc[-1]
    else:
        t1 = t0 + pd.Timedelta(minutes=minutos)
        if t1 > g.index[-1]:
            return np.nan
        p1 = g.loc[:t1].iloc[-1]
    return float(direccion * (p1 - p0))


def estudio(velas: pd.DataFrame, eventos: pd.DataFrame, n_baseline: int = 5, seed: int = 0, atr=None) -> pd.DataFrame:
    """eventos: columnas `Datetime` y `dir` (+1 largo / -1 corto). Baseline: mismo dia, hora aleatoria dentro de +-2h
    del evento, misma direccion, sin otro evento ese minuto. Devuelve por horizonte: media evento, media baseline,
    diferencia, t-stat de Welch y p-valor bootstrap.
    """
    rng = np.random.default_rng(seed)
    velas = velas.sort_values("Datetime")
    velas = velas.assign(_f=velas["Datetime"].dt.date)
    dias = {f: g for f, g in velas.groupby("_f")}
    ev_t = set(eventos["Datetime"])
    out = []
    for h, mins in HORIZONTES.items():
        re, rb = [], []
        for _, e in eventos.iterrows():
            g = dias.get(e["Datetime"].date())
            if g is None:
                continue
            a = _retorno_fwd(g, e["Datetime"], mins, int(e["dir"]))
            if np.isnan(a):
                continue
            re.append(a)
            cand = g[(g["Datetime"] >= e["Datetime"] - pd.Timedelta(hours=2)) &
                     (g["Datetime"] <= e["Datetime"] + pd.Timedelta(hours=2)) & (~g["Datetime"].isin(ev_t))]["Datetime"].values
            if len(cand):
                for t in rng.choice(cand, min(n_baseline, len(cand)), replace=False):
                    b = _retorno_fwd(g, pd.Timestamp(t).tz_localize(e["Datetime"].tz) if pd.Timestamp(t).tzinfo is None else pd.Timestamp(t),
                                     mins, int(e["dir"]))
                    if not np.isnan(b):
                        rb.append(b)
        re, rb = np.array(re), np.array(rb)
        if len(re) < 5 or len(rb) < 5:
            out.append(dict(horizonte=h, n_evento=len(re), n_base=len(rb)))
            continue
        dif = re.mean() - rb.mean()
        se = np.sqrt(re.var(ddof=1) / len(re) + rb.var(ddof=1) / len(rb))
        boot = np.array([rng.choice(re, len(re)).mean() - rng.choice(rb, len(rb)).mean() for _ in range(2000)])
        p = float(2 * min((boot <= 0).mean(), (boot >= 0).mean()))
        out.append(dict(horizonte=h, n_evento=len(re), n_base=len(rb), media_evento=float(re.mean()),
                        media_base=float(rb.mean()), diferencia=float(dif), t_welch=float(dif / se) if se > 0 else np.nan,
                        p_bootstrap=p, ic90_lo=float(np.percentile(boot, 5)), ic90_hi=float(np.percentile(boot, 95))))
    return pd.DataFrame(out).set_index("horizonte")
