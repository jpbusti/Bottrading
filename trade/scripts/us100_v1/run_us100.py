"""Corre las 4 hipotesis del pre-registro US100 v1 y evalua los 7 criterios. Escribe resultados/us100_v1/*.csv y resumen.json.
Uso: python scripts/us100_v1/run_us100.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.us100_v1 import motor_us100 as m  # noqa: E402
from validacion import pf_inference as pi  # noqa: E402
from validacion.placebo import p_valor, placebo_direccion, placebo_nivel  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "resultados" / "us100_v1"
OUT.mkdir(parents=True, exist_ok=True)
HIPS = ["H1", "H2", "H3", "H4"]
N_TIMING = 200


def pf(t):
    return pi.pf(t.R.values) if len(t) else float("nan")


def grilla(hip, dias):
    filas = []
    thrs = (0.75, 1.0, 1.25)
    if hip == "H2":
        extra = [dict(slm=v) for v in (0.15, 0.20, 0.25)]
    elif hip == "H4":
        extra = [dict()]                    # el TP es el POC: la rejilla solo varia el umbral
    else:
        extra = [dict(tpm=v) for v in (1.0, 1.5, 2.0)]
    for th in thrs:
        for ex in extra:
            t = m.correr(hip, dias, thr=th, **ex)
            filas.append(dict(thr=th, **ex, n=len(t), PF=pf(t), expR=t.R.mean() if len(t) else np.nan))
    return pd.DataFrame(filas)


def main():
    dias = m.cargar_dias()
    por_fecha = {x.fecha: x for x in dias}
    print(f"dias validos {len(dias)}  {dias[0].fecha} -> {dias[-1].fecha}  costo base {m.COSTO_BASE} estres {m.COSTO_ESTRES}")
    resumen = {}
    for hip in HIPS:
        t = m.correr(hip, dias)
        t.to_csv(OUT / f"trades_{hip}.csv", index=False)
        r = t.R.values
        res = pi.resumen_r(r, grupos=t.fecha.values)
        anios = t.groupby("anio").apply(lambda g: pd.Series(dict(n=len(g), PF=pi.pf(g.R.values), expR=g.R.mean())), include_groups=False)
        anios.to_csv(OUT / f"anios_{hip}.csv")
        elegibles = anios[anios.n >= 30]
        pct_anios = float((elegibles.PF > 1).mean()) if len(elegibles) else float("nan")
        t3 = m.correr(hip, dias, costo=m.COSTO_ESTRES)
        # placebos
        pn = placebo_nivel(r, lambda lag: m.correr(hip, dias, lag=lag).R.values, lags=(2, 3, 5, 10))
        pt = np.array([pi.pf(m.placebo_timing_r(t, por_fecha, seed)) for seed in range(N_TIMING)])
        p_t = p_valor(res["PF"], pt)
        pdir = placebo_direccion(r, m.correr(hip, dias, invertir=True).R.values)
        g = grilla(hip, dias)
        g.to_csv(OUT / f"rejilla_{hip}.csv", index=False)
        n_ok = int((g.PF >= 1.15).sum())
        sin_anio = {int(y): pi.pf(t[t.anio != y].R.values) for y in sorted(t.anio.unique())}
        mitades = {"2018-2022": pf(t[t.anio <= 2022]), "2023-2026": pf(t[t.anio >= 2023])}
        estacion = {"verano": pf(t[t.verano]), "invierno": pf(t[~t.verano])}
        crit = {
            "1_PF>=1.15": bool(res["PF"] >= 1.15),
            "2_IC90_PF_inf>1": bool(res["pf_lo_dia"] > 1.0),
            "3_IC90_exp_inf>0": bool(res["exp_lo"] > 0),
            "4_>=60%_anios_PF>1": bool(pct_anios >= 0.6),
            "5_placebos": bool(pn["supera"] and p_t <= 0.05 and pdir["supera"]),
            "6_PF_costo3>1": bool(pf(t3) > 1.0),
            "7_rejilla_>=2_puntos_PF>=1.15": bool(n_ok >= 2),
        }
        resumen[hip] = dict(
            n=int(res["n"]), win=res["win"], PF=res["PF"], expR=res["expR"], PF_IC90=[res["pf_lo_dia"], res["pf_hi_dia"]],
            exp_IC90=[res["exp_lo"], res["exp_hi"]], maxDD_R=res["DD_R"], PF_costo3=pf(t3),
            pct_anios_PF_gt1=pct_anios, placebo_nivel=dict(pf_real=pn["pf_real"], pf_placebo=pn["pf_placebo"], supera=pn["supera"]),
            placebo_timing=dict(pf_med=float(np.nanmedian(pt)), pf_p95=float(np.nanpercentile(pt, 95)), p=p_t),
            placebo_direccion=dict(pf_invertido=pdir["pf_invertido"], supera=pdir["supera"]),
            rejilla_puntos_ok=n_ok, rejilla_n=len(g), sin_anio=sin_anio, mitades=mitades, estacion=estacion,
            criterios=crit, APROBADA=bool(all(crit.values())))
    (OUT / "resumen.json").write_text(json.dumps(resumen, indent=1, default=float), encoding="utf-8")
    for h, v in resumen.items():
        print(f"\n== {h}: n={v['n']} win={v['win']:.1f}% PF={v['PF']:.3f} expR={v['expR']:.3f} "
              f"IC90 PF=[{v['PF_IC90'][0]:.3f},{v['PF_IC90'][1]:.3f}] IC90 exp=[{v['exp_IC90'][0]:.3f},{v['exp_IC90'][1]:.3f}] "
              f"DD={v['maxDD_R']:.1f}R PF(costo3)={v['PF_costo3']:.3f}")
        print("   anios PF>1:", f"{v['pct_anios_PF_gt1']:.0%}", "| placebo nivel", {k: round(x, 3) for k, x in v['placebo_nivel']['pf_placebo'].items()},
              "| timing p=", round(v['placebo_timing']['p'], 3), "med", round(v['placebo_timing']['pf_med'], 3),
              "| dir invertida PF", round(v['placebo_direccion']['pf_invertido'], 3))
        print("   rejilla ok:", v['rejilla_puntos_ok'], "/", v['rejilla_n'], "| mitades", {k: round(x, 3) for k, x in v['mitades'].items()},
              "| estacion", {k: round(x, 3) for k, x in v['estacion'].items()})
        print("   criterios:", v['criterios'], "->", "APROBADA" if v['APROBADA'] else "NO APROBADA")


if __name__ == "__main__":
    main()
