"""Corre la validacion G2 pre-registrada.
Uso (desde la raiz): python scripts/g2/run_validacion.py   (requiere haber corrido extraer_contratos.py)
Opcional: <carpeta_pkl> <carpeta_salida>; por defecto data/processed -> resultados/g2"""
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import motor_g2 as m

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("run")
RAIZ = Path(__file__).resolve().parents[2]
PKL = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "processed"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "resultados" / "g2"
OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 220)

INSTR = {
    # nombre: (pkl, costo_base_pts, desde, hasta)
    "NQ_2016_2021": ("NQ_contratos_rth.pkl", 3.0, None, None),
    "ES_2016_2025": ("ES_contratos_rth.pkl", 1.25, None, dt.date(2025, 10, 6)),
    "ES_ultimo_anio": ("ES_contratos_rth.pkl", 1.25, dt.date(2025, 10, 7), None),
}
METODOS_DECISION = ["ATR", "PCT"]


def evaluar(t, tp, costo):
    r = m.resumen(t, costo)
    if r["n"] == 0:
        return {}, {}
    ya = m.por_anio(t, costo)
    ya_ok = ya[ya.n >= 30]
    frac = (ya_ok.PF > 1).mean() if len(ya_ok) else 0.0
    rp = m.resumen(tp, costo) if len(tp) else {"PF": np.nan}
    c = dict(
        C1_PF_ge_1_15=bool(r["PF"] >= 1.15),
        C2_IC90_exp_gt0=bool(r["exp_lo"] > 0),
        C3_IC90_PF_gt1=bool(r["pf_lo"] > 1.0),
        C4_anios_PF_gt1_ge60=bool(frac >= 0.6 and len(ya_ok) > 0),
        C5_PF_gt_placebo=bool(r["PF"] > rp["PF"]),
    )
    c["TODOS"] = all(c.values())
    r.update(PF_placebo=rp["PF"], frac_anios=frac, anios_eval=len(ya_ok))
    return r, c


mercados = {}
resumen_total = {}
filas_decision = []
for nombre, (pkl, costo, desde, hasta) in INSTR.items():
    if pkl not in mercados:
        df = pd.read_pickle(PKL / pkl)
        mercados[pkl] = m.Mercado(df, pkl.split("_")[0])
    M = mercados[pkl]
    log.info("=== %s (costo base %.2f pts) ===", nombre, costo)
    res = {}
    for met in ["ATR", "PCT", "FIJO"]:
        t = M.correr(met, lag=1, desde=desde, hasta=hasta)
        tp = M.correr(met, lag=2, desde=desde, hasta=hasta)
        r, c = evaluar(t, tp, costo)
        res[met] = (t, r, c)
        t.to_csv(OUT / f"trades_{nombre}_{met}.csv", index=False)
        log.info("%s %s n=%s PF=%.3f expR=%+.3f IC90exp=[%+.3f,%+.3f] IC90PF=[%.2f,%.2f] win=%.1f%% placebo PF=%.2f | aniosPF>1=%.0f%% (%d anios)",
                 nombre, met, r.get("n"), r.get("PF", np.nan), r.get("expR", np.nan), r.get("exp_lo", np.nan),
                 r.get("exp_hi", np.nan), r.get("pf_lo", np.nan), r.get("pf_hi", np.nan), r.get("win", np.nan),
                 r.get("PF_placebo", np.nan), 100 * r.get("frac_anios", 0), r.get("anios_eval", 0))
        log.info("   criterios: %s", c)
        filas_decision.append(dict(instr=nombre, metodo=met, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in {**r, **c}.items()}))
    # ---- sensibilidades (informativas) sobre los metodos de decision
    for met in METODOS_DECISION:
        t = res[met][0]
        if len(t) == 0:
            continue
        log.info("--- %s %s: sensibilidad de costo / roll / fill / filtro / anual ---", nombre, met)
        for f in (0.5, 1.0, 2.0):
            r = m.resumen(t, costo * f)
            log.info("costo x%.1f: PF=%.3f expR=%+.3f IC90exp lo=%+.3f", f, r["PF"], r["expR"], r["exp_lo"])
        for k in (0, 1, 2, 3):
            tk = t[t.dsr >= k]
            r = m.resumen(tk, costo)
            log.info("omitir %d dia(s) tras roll: n=%d PF=%.3f expR=%+.3f", k, r["n"], r["PF"], r["expR"])
        tt = M.correr(met, lag=1, through=0.5, desde=desde, hasta=hasta)
        r = m.resumen(tt, costo)
        log.info("fill exige 0.5 pt (x escala) a traves del nivel: n=%d PF=%.3f expR=%+.3f IC90exp lo=%+.3f", r["n"], r["PF"], r["expR"], r["exp_lo"])
        tpost = M.correr(met, lag=1, modo_filtro="post", desde=desde, hasta=hasta)
        r = m.resumen(tpost, costo)
        log.info("filtros hora/POC en modo 'post': n=%d PF=%.3f expR=%+.3f IC90exp lo=%+.3f", r["n"], r["PF"], r["expR"], r["exp_lo"])
        ya = m.por_anio(t, costo)
        log.info("por anio:\n%s", ya.round(3).to_string(index=False))
        mc = m.monte_carlo_dd(m.r_mult(t, costo))
        log.info("Monte Carlo (bloques 20): %s", {k: round(float(v), 2) for k, v in mc.items()})
        # desglose por nivel y direccion
        R = pd.Series(m.r_mult(t, costo))
        g = pd.DataFrame({"nivel": t.nivel.values, "dir": t.dir.values, "R": R.values})
        log.info("por nivel:\n%s", g.groupby("nivel").R.agg(["count", "mean"]).round(3).to_string())
        log.info("por direccion:\n%s", g.groupby("dir").R.agg(["count", "mean"]).round(3).to_string())

pd.DataFrame(filas_decision).to_csv(OUT / "resumen_decision.csv", index=False)

# ---- veredicto G2 (NQ fuera de tiempo + ES 2016-2025, ambos metodos)
dec = pd.DataFrame(filas_decision)
dec = dec[dec.instr.isin(["NQ_2016_2021", "ES_2016_2025"]) & dec.metodo.isin(METODOS_DECISION)]
log.info("VEREDICTO G2: %s", "APROBADO" if bool(dec["TODOS"].all()) and len(dec) == 4 else "NO APROBADO")
log.info("\n%s", dec[["instr", "metodo", "n", "PF", "expR", "exp_lo", "pf_lo", "frac_anios", "PF_placebo", "C1_PF_ge_1_15",
                      "C2_IC90_exp_gt0", "C3_IC90_PF_gt1", "C4_anios_PF_gt1_ge60", "C5_PF_gt_placebo", "TODOS"]].to_string(index=False))
