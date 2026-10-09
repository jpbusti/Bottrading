"""Estudio de eventos US100 ORB (v2): evento = ORB + VWAP + volumen + retest, entrada al CIERRE de la barra de retest.

Sin backtest, sin SL/TP, sin costos. Parametros del pre-registro (config.yaml). Datos: USTEC_1m_clean_2018_2026.csv (ET).
Retorno forward direccional en %; baseline = 1000 sorteos por evento entre las barras del MISMO dia y MISMA hora ET de la entrada
(misma direccion, excluida la barra de entrada). Estadistica pareada: diferencia por evento = evento - media(sorteos).
Uso: python scripts/us100_orb/event_study_v2.py
"""
from __future__ import annotations

import copy
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_orb.run_backtest import CARPETA, OUT, cargar  # noqa: E402

HORIZ = {"30m": 6, "1h": 12, "2h": 24, "cierre": None}      # barras de 5m desde la barra de entrada
N_SORTEOS, N_BOOT, BLOQUE_MAX, SEED = 1000, 5000, 20, 20261009
MIN_BARRAS_DIA = 74                                          # dia completo (78 barras): fuera medias sesiones y dias con huecos

# FOMC (fecha de decision) 2018-2026. [VERIFICAR] escritas a mano, sin fuente en el repo.
FOMC = """2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-03-03 2020-03-15 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09""".split()
FOMC = {pd.Timestamp(x).date() for x in FOMC}


def excluidos(b: pd.DataFrame, calendario: bool = True) -> tuple[dict, pd.DataFrame]:
    """Dias a ignorar y motivo. Devuelve ({fecha: motivo}, tabla diaria)."""
    g = b.groupby("fecha").agg(abre=("open", "first"), cierra=("close", "last"), n=("close", "size"), atr=("atr_d", "first"))
    g["gap"] = g.abre / g.cierra.shift(1) - 1
    umbral = g.atr.expanding(min_periods=100).quantile(0.10).shift(1)      # percentil 10 con historia previa (sin look-ahead)
    mot = {}
    for f, r in g.iterrows():
        m = []
        if r.n < MIN_BARRAS_DIA:
            m.append("sesion incompleta/media")
        if calendario:
            d = pd.Timestamp(f)
            if f in FOMC:
                m.append("FOMC")
            if d.weekday() == 4 and 15 <= d.day <= 21:
                m.append("OPEX")
            if d.weekday() == 4 and d.day <= 7:
                m.append("NFP (1er viernes)")
        if np.isfinite(r.gap) and abs(r.gap) > 0.01:
            m.append("gap>1%")
        if np.isfinite(r.atr) and np.isfinite(umbral[f]) and r.atr < umbral[f]:
            m.append("ATR<p10")
        if not np.isfinite(r.atr):
            m.append("sin ATR")
        if m:
            mot[f] = "|".join(m)
    return mot, g


def eventos(b: pd.DataFrame, cfg: dict, mot: dict, vwap=True, vol=True, retest=True) -> pd.DataFrame:
    tf = cfg["datos"]["timeframe_min"]
    n_or = cfg["opening_range"]["minutos"] // tf
    nb = cfg["filtros"]["vwap_pendiente"]["barras"]
    mult = cfg["filtros"]["volumen"]["multiplo"]
    mr = cfg["filtros"]["retest"]["max_barras"]
    H, L, C, VW, VR = b.high.values, b.low.values, b.close.values, b.vwap.values, b.vol_rel.values
    fechas = b.fecha.values
    ini = np.r_[0, np.flatnonzero(fechas[1:] != fechas[:-1]) + 1]
    fin = np.r_[ini[1:], len(fechas)]
    ult_idx = 10 * 12          # barra de las 15:00 (09:30 + 330 min = 66 barras) -> indice 66
    ult_idx = 66
    filas = []
    for a, z in zip(ini, fin):
        f = fechas[a]
        if f in mot:
            continue
        orh, orl = H[a:a + n_or].max(), L[a:a + n_or].min()
        j = next((q for q in range(a + n_or, min(z - 1, a + ult_idx + 1)) if C[q] > orh or C[q] < orl), None)
        if j is None:
            continue
        d = 1 if C[j] > orh else -1
        nivel = orh if d == 1 else orl
        if vwap and (j - nb < a or not np.isfinite(VW[j]) or not np.isfinite(VW[j - nb]) or d * (VW[j] - VW[j - nb]) <= 0):
            continue
        if vol and not (VR[j] > mult):
            continue
        conf = j
        if retest:
            conf = None
            for q in range(j + 1, min(j + mr, z - 1) + 1):
                toca = L[q] <= nivel if d == 1 else H[q] >= nivel
                if toca:
                    if d * (C[q] - nivel) > 0:
                        conf = q               # toca el nivel y cierra del lado correcto
                    break                      # toca y cierra del lado equivocado: invalida
                if d * (C[q] - nivel) <= 0:
                    break
            if conf is None:
                continue
            if conf - a > ult_idx:
                continue
        filas.append(dict(fecha=f, d=d, i_a=a, i_z=z, i_ent=conf, ts_entrada=b.index[conf] + pd.Timedelta(minutes=tf),
                          precio=C[conf], orh=orh, orl=orl, vwap=VW[conf], atr_d=b.atr_d.values[conf]))
    return pd.DataFrame(filas)


def _fwd(C, i_ent, i_z, d, pasos, idx_ref=None):
    """Retorno forward direccional desde el cierre de la barra `idx_ref` (o i_ent). NaN si el horizonte pasa el cierre."""
    k = i_ent if idx_ref is None else idx_ref
    t = (i_z - 1) if pasos is None else k + pasos
    if t > i_z - 1 or t <= k:
        return np.nan
    return d * (C[t] - C[k]) / C[k]


def retornos(b: pd.DataFrame, ev: pd.DataFrame, rng, modo: str = "post") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorno forward del evento y media de 1000 sorteos (misma fecha y hora ET) por horizonte.

    modo="literal": candidatos = todas las barras de esa hora (salvo la de entrada). Sesgado: las barras ANTERIORES a la ruptura
      tienen en su ventana forward el propio movimiento de la ruptura, en la direccion del evento (sesgo alcista del baseline).
    modo="post": candidatos = barras de esa hora POSTERIORES a la barra de entrada (misma direccion): sin informacion del evento."""
    C, hora = b.close.values, b.index.hour.values
    re, rb = {h: [] for h in HORIZ}, {h: [] for h in HORIZ}
    for r in ev.itertuples():
        cand = [q for q in range(r.i_a, r.i_z) if hora[q] == hora[r.i_ent] and q != r.i_ent and (modo == "literal" or q > r.i_ent)]
        for h, p in HORIZ.items():
            re[h].append(_fwd(C, r.i_ent, r.i_z, r.d, p))
            vals = np.array([_fwd(C, q, r.i_z, r.d, p) for q in cand])
            vals = vals[np.isfinite(vals)]
            rb[h].append(rng.choice(vals, N_SORTEOS, replace=True).mean() if len(vals) and np.isfinite(re[h][-1]) else np.nan)
    return pd.DataFrame(re), pd.DataFrame(rb)


def boot_bloques(x: np.ndarray, rng) -> tuple[float, float, float]:
    n = len(x)
    L = max(1, min(BLOQUE_MAX, n // 4))
    nb = int(np.ceil(n / L))
    starts = rng.integers(0, n - L + 1, (N_BOOT, nb))
    m = np.array([np.concatenate([x[s:s + L] for s in row])[:n].mean() for row in starts])
    return float(np.percentile(m, 5)), float(np.percentile(m, 95)), float((m <= 0).mean())


def comparar(re: pd.DataFrame, rb: pd.DataFrame, rng) -> pd.DataFrame:
    filas = []
    for h in HORIZ:
        ok = re[h].notna() & rb[h].notna()
        e, bs = re.loc[ok, h].values * 100, rb.loc[ok, h].values * 100
        n = len(e)
        if n < 3:
            filas.append(dict(horizonte=h, n=n))
            continue
        dif = e - bs
        t, p2 = stats.ttest_1samp(dif, 0.0)
        p1 = p2 / 2 if t > 0 else 1 - p2 / 2
        lo, hi, pb = boot_bloques(dif, rng)
        filas.append(dict(horizonte=h, n=n, ret_evento_pct=e.mean(), ret_base_pct=bs.mean(), dif_pct=dif.mean(), t=t,
                          p_unilateral=p1, p_bilateral=p2, boot_ic90_lo=lo, boot_ic90_hi=hi, boot_p_unilat=pb,
                          edge=bool(p1 < 0.10 and dif.mean() > 0)))
    return pd.DataFrame(filas)


def main():
    sin_vol = "--sin-volumen" in sys.argv
    cfg = cargar_config(CARPETA)
    cfg["datos"]["fuente"] = "us100"
    if sin_vol:                                    # pre-registro v2: unico cambio = sin filtro de volumen
        cfg["filtros"]["volumen"]["activo"] = False
    sufijo = "_sinvol" if sin_vol else ""
    b = cargar(cfg)
    rng = np.random.default_rng(SEED)
    mot, g = excluidos(b)
    mot_sin, _ = excluidos(b, calendario=False)
    print(f"Dias en datos: {len(g)} | excluidos: {len(mot)} (sin calendario: {len(mot_sin)})")
    razones = pd.Series([x for v in mot.values() for x in v.split("|")]).value_counts()
    print(razones.to_string())
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    resumen = {}
    vo1 = 0 if sin_vol else 1
    etapas = {"completo": (mot, 1, vo1, 1), "completo_sin_calendario": (mot_sin, 1, vo1, 1),
              "ORB_crudo": (mot, 0, 0, 0), "+VWAP": (mot, 1, 0, 0), "+VWAP+volumen": (mot, 1, 1, 0)}
    if sin_vol:
        etapas.pop("+VWAP+volumen")
    for nombre, (mo, vw, vo, rt) in etapas.items():
        ev = eventos(b, cfg, mo, vw, vo, rt)
        print(f"\n=== {nombre}: {len(ev)} eventos ({(ev.d == 1).sum() if len(ev) else 0} long / {(ev.d == -1).sum() if len(ev) else 0} short)")
        if len(ev) < 3:
            resumen[nombre] = (ev, None)
            continue
        tabs = {}
        for modo in ("post", "literal"):
            re, rb = retornos(b, ev, rng, modo)
            tabs[modo] = comparar(re, rb, rng)
            print(f"-- baseline {modo}")
            print(tabs[modo].round(4).to_string(index=False))
            if nombre == "completo" and modo == "post":
                e = ev.drop(columns=["i_a", "i_z", "i_ent"]).join(re.add_prefix("ret_")).join(rb.add_prefix("base_"))
                e.to_csv(OUT / f"event_study_v2{sufijo}_eventos.csv", index=False)
        resumen[nombre] = (ev, tabs)
    pd.to_pickle({k: (v[0].drop(columns=["i_a", "i_z", "i_ent"], errors="ignore"), v[1]) for k, v in resumen.items()}, OUT / f"event_study_v2{sufijo}.pkl")
    ev = resumen["completo"][0]
    print("\nPor ano:\n", pd.Series(pd.to_datetime(ev.fecha).dt.year).value_counts().sort_index().to_string())
    print("Por hora ET de entrada:\n", pd.Series(ev.ts_entrada.dt.hour).value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
