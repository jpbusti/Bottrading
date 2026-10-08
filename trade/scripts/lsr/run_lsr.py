"""Corre LSR v1 pre-registrado. Uso: python run_lsr.py <carpeta_pkl> <carpeta_salida>"""
import sys, logging
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_lsr as m

logging.basicConfig(level=logging.WARNING)
PKL, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
CEN = (1.0, 1.75)
LOG = open(OUT / "resultado_lsr.log", "w", encoding="utf-8")
def P(*a):
    s = " ".join(str(x) for x in a); print(s); LOG.write(s + "\n"); LOG.flush()
def T(df, nd=3): P(df.round(nd).to_string()); 
def fila(nombre, df, mult, f=1.0):
    r = m.resumen(df, mult, f); r["variante"] = nombre; return r
COLS = ["variante", "n", "PF_bruto", "PF_neto", "PF_lo90", "PF_hi90", "PF_usd", "expR", "win", "DD_R", "DD_pct", "DD_pct_1"]
def tabla(filas): return pd.DataFrame(filas).reindex(columns=COLS).set_index("variante")
SUB = [("2016-18", 2016, 2018), ("2019-21", 2019, 2021), ("2022-24", 2022, 2024), ("2025-26", 2025, 2026)]

veredictos = {}
for inst in ["NQ", "ES"]:
    mult = m.MULT[inst]
    M = m.Mercado(pd.read_pickle(PKL / f"{inst}_contratos_ext.pkl"), inst)
    P("\n" + "=" * 100 + f"\n{inst}  dias={len(M.fechas)}  {M.fechas[0]} -> {M.fechas[-1]}\n" + "=" * 100)
    A = m.generar(M, "A"); B = m.generar(M, "B"); E = m.generar(M, "A", estructural=True, grid=False, extra_ks=())
    A.to_csv(OUT / f"trades_{inst}_A.csv", index=False); B.to_csv(OUT / f"trades_{inst}_B.csv", index=False)
    E.to_csv(OUT / f"trades_{inst}_A_estructural.csv", index=False)
    first = A.fecha.min() if len(A) else None
    P(f"Bloque A: trades/combo={len(A)//max(A.combo.nunique(),1)}  primer trade={first}")

    # ---- 1) rejilla bloque A / B (descriptivo, toda la muestra: NO decide)
    for nm, D in (("A", A), ("B", B)):
        if len(D) == 0: P(f"Bloque {nm}: sin trades"); continue
        P(f"\n--- Bloque {nm}: rejilla k/m completa (descriptivo; no decide) ---")
        T(tabla([fila(str(c), D[D.combo == c], mult) for c in sorted(D.combo.unique(), key=str)]))
    if len(E):
        P("\n--- Variante estructural (SL extremo del barrido, TP lado opuesto del dia previo) ---")
        T(tabla([fila("A_estructural", E, mult)]))

    # ---- 2) walk-forward bloque A y B
    res = {}
    for nm, D in (("A", A), ("B", B)):
        if len(D) == 0: continue
        oos, folds = m.walk_forward(D)
        res[nm] = (oos, folds)
        P(f"\n--- Walk-forward expansivo bloque {nm} (folds) ---"); T(folds)
        oos.to_csv(OUT / f"wf_oos_{inst}_{nm}.csv", index=False)
        r = fila(f"WF_OOS_{nm}", oos, mult)
        if len(oos):
            p50, p95 = m.mc_dd(m.Rnet(oos))
            r["DD_MC_p50"], r["DD_MC_p95"] = p50, p95
        P(f"WF OOS agrupado {nm}:"); P({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "variante"})
        res[nm] = (oos, folds, r)

    # ---- 3) subperiodos y fragilidad (WF OOS A; combo central A en toda la muestra)
    if "A" in res:
        oos = res["A"][0]
        P("\n--- Subperiodos: combo central (1.0,1.75) toda la muestra | WF-OOS ---")
        c = A[A.combo == CEN]; fil = []
        for nm, a, z in SUB:
            fil.append(fila(f"central {nm}", c[(c.anio >= a) & (c.anio <= z)], mult))
            fil.append(fila(f"WF-OOS {nm}", oos[(oos.anio >= a) & (oos.anio <= z)], mult))
        T(tabla(fil).dropna(how="all"))
        P("\n--- Fragilidad: PF WF-OOS agrupado sin cada anio ---")
        base = m.pf(m.Rnet(oos)) if len(oos) else np.nan
        fr = []
        for y in sorted(oos.anio.unique()):
            s = oos[oos.anio != y]; fr.append(dict(sin_anio=y, n=len(s), PF=m.pf(m.Rnet(s)), dPF=m.pf(m.Rnet(s)) - base))
        T(pd.DataFrame(fr).set_index("sin_anio"))
        P("PF por anio WF-OOS:"); T(pd.DataFrame([dict(anio=y, n=len(g), PF=m.pf(m.Rnet(g)), expR=m.Rnet(g).mean()) for y, g in oos.groupby("anio")]).set_index("anio"))

    # ---- 4) robustez: sensibilidades (combo central + rejilla A)
    P("\n--- Sensibilidades (combo central 1.0/1.75 salvo nota; toda la muestra) ---")
    s = []
    cen = lambda D: D[D.combo == CEN]
    s.append(fila("base", cen(A), mult))
    s.append(fila("costos x0.5", cen(A), mult, 0.5)); s.append(fila("costos x2", cen(A), mult, 2.0))
    s.append(fila("reclaim N=3", cen(m.generar(M, "A", N=3)), mult)); s.append(fila("reclaim N=5", cen(m.generar(M, "A", N=5)), mult))
    s.append(fila("entrada apertura sig.", cen(m.generar(M, "A", modo_entrada="open")), mult))
    s.append(fila("ventana solo 9:45-12:00", cen(m.generar(M, "A", ventanas=((585, 720),))), mult))
    s.append(fila("ventana solo 14:00-15:30", cen(m.generar(M, "A", ventanas=((840, 930),))), mult))
    s.append(fila("ventana 10:00-11:30", cen(m.generar(M, "A", ventanas=((600, 690),))), mult))
    s.append(fila("ventana 9:45-15:30 continua", cen(m.generar(M, "A", ventanas=((585, 930),))), mult))
    s.append(fila("ventana 12:00-14:00 (prohibida, ref.)", cen(m.generar(M, "A", ventanas=((720, 840),))), mult))
    s.append(fila("sin filtros regimen/calendario", cen(m.generar(M, "A", filtros=False)), mult))
    s.append(fila("PLACEBO niveles D-2", cen(m.generar(M, "A", lag=2)), mult))
    T(tabla(s))
    # rejilla: cuantos puntos PF>=1.15 / lo90>1
    g = [m.resumen(A[A.combo == c], mult) for c in A.combo.unique() if isinstance(c, tuple) and c != m.REF]
    P(f"Rejilla A: puntos con PF_neto>=1.15: {sum(x['PF_neto']>=1.15 for x in g)}/9 ; con lo90>1: {sum(x['PF_lo90']>1 for x in g)}/9 ; PF_neto min/max {min(x['PF_neto'] for x in g):.3f}/{max(x['PF_neto'] for x in g):.3f}")

    # ---- 5) veredicto del instrumento (WF-OOS bloque A)
    if "A" in res:
        r = res["A"][2]
        ok = dict(PF=r["PF_neto"] >= 1.15, lo90=r["PF_lo90"] > 1.0, n=r["n"] >= 300, DD=r.get("DD_pct", 99) < 20)
        P(f"\nCRITERIOS {inst} (WF-OOS A): {ok}")
        veredictos[inst] = (all(ok.values()), r)
    if "B" in res:
        r = res["B"][2]
        P(f"Bloque B {inst} WF-OOS: PF={r['PF_neto']:.3f} lo90={r['PF_lo90']:.3f} n={r['n']} -> {'INCLUIR' if (r['PF_neto']>=1.15 and r['PF_lo90']>1.0) else 'EXCLUIR'}")
P("\nVEREDICTOS:", {k: v[0] for k, v in veredictos.items()})
