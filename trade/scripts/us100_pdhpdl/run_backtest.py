"""Backtest US100 PDH/PDL (rejilla k x m completa) + costos de estres y costos por anio.

Uso (desde trade/):  python scripts/us100_pdhpdl/run_backtest.py [--fuente us100|nq]
Salida: resultados/us100_pdhpdl/trades_<fuente>.csv y resumen en pantalla. Placebos y walk-forward van en sus scripts.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_pdhpdl import analysis, datos, simulador, strategy  # noqa: E402
from validacion import pf_inference as pi  # noqa: E402

CARPETA = Path(__file__).resolve().parent
OUT = CARPETA.parents[1] / "resultados" / "us100_pdhpdl"


def cargar(cfg):
    return datos.preparar(cfg)


def costos_alt(b, sen, cfg):
    """PF del combo central con spread de estres y con el spread mediano observado de cada anio."""
    cen = [tuple(cfg["riesgo"]["combo_central"])]
    c = cfg["costos"]
    out = {}
    est = simulador.simular_trades(b, sen, cfg, combos=cen, costo=simulador.costo_pts(cfg, spread=c["spread_pts_estres"]))
    out["estres"] = dict(costo=simulador.costo_pts(cfg, spread=c["spread_pts_estres"]), PF=pi.pf(est.R.values), n=len(est))
    sp = datos.spread_por_anio(b)
    if len(sp):
        ca = {int(y): simulador.costo_pts(cfg, spread=float(s)) for y, s in sp.items()}
        pa = simulador.simular_trades(b, sen, cfg, combos=cen, costo_anio=ca)
        out["por_anio"] = dict(costos=ca, PF=pi.pf(pa.R.values), PF_anio=pa.groupby("anio").R.apply(lambda r: pi.pf(r.values)).to_dict())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["us100", "nq"])
    a = ap.parse_args()
    cfg = cargar_config(CARPETA)
    if a.fuente:
        cfg["datos"]["fuente"] = a.fuente
    b = cargar(cfg)
    sen = strategy.generar_senales(b, cfg)
    print(f"fuente={cfg['datos']['fuente']} dias={b.fecha.nunique()} senales={len(sen)} (cortos {int((sen.d == -1).sum())}, largos {int((sen.d == 1).sum())})")
    tr = simulador.simular_trades(b, sen, cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    tr.to_csv(OUT / f"trades_{cfg['datos']['fuente']}.csv", index=False)
    res = analysis.resumen_central(tr, cfg)
    rob = analysis.robustez(tr, cfg)
    ca = costos_alt(b, sen, cfg)
    analysis.imprimir(res, rob, analysis.criterios(res, rob, None, cfg))
    print("\nMotivos de salida (central):", analysis.central(tr, cfg).motivo.value_counts().to_dict())
    print("Costo base (pts):", simulador.costo_pts(cfg), "| estres:", ca["estres"])
    if "por_anio" in ca:
        print("Costos por anio (pts):", ca["por_anio"]["costos"], "\nPF con costo por anio:", round(ca["por_anio"]["PF"], 3),
              {k: round(v, 3) for k, v in ca["por_anio"]["PF_anio"].items()})


if __name__ == "__main__":
    main()
