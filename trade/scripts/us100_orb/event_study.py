"""Fase 0 de la metodologia: estudio de eventos de US100 ORB. Mide el retorno forward tras el evento vs un baseline; NO simula SL/TP ni costos.

Evento = senal completa de strategy.generar_senales (ruptura del OR + VWAP + volumen + retest), entrada = apertura de la barra siguiente
a la confirmacion. Retorno forward = d x (precio_horizonte - apertura_entrada), en puntos y en unidades de ATR diario previo.
Horizontes desde la entrada: 30 min, 1 h, 2 h y cierre (barra de salida forzada). Si el horizonte excede el cierre, el evento no cuenta.

Baselines (misma direccion que el evento, mismo instrumento):
  B1 "misma hora": la misma hora del dia en 5 dias SIN evento sorteados (controla efecto hora/deriva intradia).
  B2 "mismo dia":  5 barras sorteadas del mismo dia (entre la 1a barra tras el OR y la ultima entrada), distintas a la entrada.
Estadistica: diferencia pareada evento - media(baseline); t pareado (p con t de Student); bootstrap por bloques de 20 eventos
consecutivos (IC90 y p). Uso: python scripts/us100_orb/event_study.py [--fuente us100|nq]
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_orb import simulador, strategy  # noqa: E402
from scripts.us100_orb.run_backtest import CARPETA, OUT, cargar  # noqa: E402

HORIZONTES = {"30m": 30, "1h": 60, "2h": 120, "cierre": None}
N_BASE, BLOQUE, N_BOOT = 5, 20, 5000


def retornos(b: pd.DataFrame, cfg: dict, i_ent: np.ndarray, d: np.ndarray, fechas: np.ndarray, sal: pd.Series, mins) -> np.ndarray:
    """Retorno forward direccional en puntos desde la apertura de la barra i_ent; NaN si no hay datos hasta el horizonte."""
    tf = cfg["datos"]["timeframe_min"]
    O, C = b.open.values, b.close.values
    i_sal = np.array([sal.get(f, -1) for f in fechas])
    i_fin = i_sal if mins is None else i_ent + mins // tf - 1
    ok = (i_sal >= i_ent) & (i_fin <= i_sal) & (i_fin >= i_ent)
    out = np.full(len(i_ent), np.nan)
    out[ok] = d[ok] * (C[i_fin[ok]] - O[i_ent[ok]])
    return out


def _bloques(x: np.ndarray, rng, n=N_BOOT, bloque=BLOQUE) -> np.ndarray:
    """Medias bootstrap con bloques moviles de `bloque` observaciones consecutivas."""
    m = len(x)
    bl = min(bloque, m)
    nb = int(np.ceil(m / bl))
    ini = rng.integers(0, m - bl + 1, size=(n, nb))
    idx = (ini[:, :, None] + np.arange(bl)).reshape(n, -1)[:, :m]
    return x[idx].mean(axis=1)


def _estadistica(ev: np.ndarray, base: np.ndarray, rng) -> dict:
    """ev: retorno por evento; base: media del baseline por evento. Diferencia pareada."""
    ok = np.isfinite(ev) & np.isfinite(base)
    ev, base = ev[ok], base[ok]
    if len(ev) < 10:
        return dict(n=len(ev))
    dif = ev - base
    t, p_t = stats.ttest_1samp(dif, 0.0)
    bs = _bloques(dif, rng)
    p_b = float(2 * min((bs <= 0).mean(), (bs >= 0).mean()))
    return dict(n=len(ev), media_evento=float(ev.mean()), media_base=float(base.mean()), diferencia=float(dif.mean()),
                t=float(t), p_t=float(p_t), p_bloques=max(p_b, 1 / N_BOOT), ic90_lo=float(np.percentile(bs, 5)),
                ic90_hi=float(np.percentile(bs, 95)), pct_pos_evento=float((ev > 0).mean() * 100))


def _baselines(b, cfg, sen, atr_e, rng, mins):
    """Devuelve (ret_evento, base_B1, base_B2) en puntos y las mismas en ATR (dict de 'pts'/'atr')."""
    tf = cfg["datos"]["timeframe_min"]
    n_or = cfg["opening_range"]["minutos"] // tf
    max_idx = (simulador._min(cfg["sesion"]["ultima_entrada"]) - simulador._min(cfg["sesion"]["inicio"])) // tf
    sal = simulador.idx_salida(b, cfg)
    fechas_b = b.fecha.values
    ini = pd.Series(np.arange(len(b)), index=fechas_b).groupby(level=0).first()
    n_dia = pd.Series(1, index=fechas_b).groupby(level=0).sum()
    dias_ok = np.array([f for f in ini.index if f in sal.index and n_dia[f] > max_idx + 1])
    con_evento = set(sen.fecha)
    libres = np.array([f for f in dias_ok if f not in con_evento])
    ev_i, ev_d, ev_f = sen.i_entrada.values, sen.d.values, sen.fecha.values
    r_ev = retornos(b, cfg, ev_i, ev_d, ev_f, sal, mins)
    off = ev_i - ini.loc[ev_f].values
    atr = b.atr_d.values
    b1_pts, b2_pts, b1_atr, b2_atr = [np.full(len(sen), np.nan) for _ in range(4)]
    for k in range(len(sen)):
        # B1: misma hora, dias sin evento
        dsel = rng.choice(libres, N_BASE, replace=False)
        pos = ini.loc[dsel].values + off[k]
        r = retornos(b, cfg, pos, np.full(N_BASE, ev_d[k]), dsel, sal, mins)
        a = atr[pos]
        b1_pts[k], b1_atr[k] = np.nanmean(r) if np.isfinite(r).any() else np.nan, np.nanmean(r / a) if np.isfinite(r).any() else np.nan
        # B2: mismo dia, otras barras
        cand = np.array([o for o in range(n_or, max_idx + 1) if o != off[k]])
        psel = ini[ev_f[k]] + rng.choice(cand, N_BASE, replace=False)
        r = retornos(b, cfg, psel, np.full(N_BASE, ev_d[k]), np.full(N_BASE, ev_f[k]), sal, mins)
        b2_pts[k], b2_atr[k] = np.nanmean(r) if np.isfinite(r).any() else np.nan, np.nanmean(r / atr[psel]) if np.isfinite(r).any() else np.nan
    return r_ev, r_ev / atr_e, dict(B1=(b1_pts, b1_atr), B2=(b2_pts, b2_atr))


def estudio(b: pd.DataFrame, cfg: dict, sen: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    atr_e = b.atr_d.values[sen.i_entrada.values]
    filas = []
    for h, mins in HORIZONTES.items():
        r_pts, r_atr, bases = _baselines(b, cfg, sen, atr_e, rng, mins)
        for bn, (bp, ba) in bases.items():
            for unidad, ev, bs in (("pts", r_pts, bp), ("ATR", r_atr, ba)):
                filas.append(dict(horizonte=h, baseline=bn, unidad=unidad, **_estadistica(ev, bs, rng)))
    return pd.DataFrame(filas)


def variantes(cfg: dict) -> dict:
    """Ablacion: el evento completo y versiones con menos filtros (para ver que aporta cada uno)."""
    out = {}
    for nombre, (vw, vol, rt) in {"ORB_crudo": (0, 0, 0), "+VWAP": (1, 0, 0), "+VWAP+volumen": (1, 1, 0), "completo(+retest)": (1, 1, 1)}.items():
        c = copy.deepcopy(cfg)
        c["filtros"]["vwap_pendiente"]["activo"] = bool(vw)
        c["filtros"]["volumen"]["activo"] = bool(vol)
        c["filtros"]["retest"]["activo"] = bool(rt)
        out[nombre] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["us100", "nq"])
    a = ap.parse_args()
    cfg = cargar_config(CARPETA)
    if a.fuente:
        cfg["datos"]["fuente"] = a.fuente
    b = cargar(cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    res_all = []
    for nombre, c in variantes(cfg).items():
        sen = strategy.generar_senales(b, c)
        sen = sen[np.isfinite(b.atr_d.values[sen.i_entrada.values])].reset_index(drop=True)
        r = estudio(b, c, sen)
        r.insert(0, "evento", nombre)
        r.insert(1, "n_eventos", len(sen))
        res_all.append(r)
        print(f"\n=== {nombre}: {len(sen)} eventos ({(sen.d == 1).sum()} largos / {(sen.d == -1).sum()} cortos), "
              f"{sen.fecha.min()} -> {sen.fecha.max()}")
        cols = ["horizonte", "baseline", "n", "media_evento", "media_base", "diferencia", "t", "p_t", "p_bloques", "ic90_lo", "ic90_hi"]
        print(r[r.unidad == "ATR"][cols].round(4).to_string(index=False))
    pd.concat(res_all).to_csv(OUT / f"event_study_{cfg['datos']['fuente']}.csv", index=False)


if __name__ == "__main__":
    main()
