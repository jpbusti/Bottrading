"""Robustez de parametros de senal, de a uno: ultima entrada y con/sin condicion de rechazo (rejilla en config.yaml).
Uso (desde trade/):  python scripts/us100_pdhpdl/run_robustez.py [--fuente us100|nq]"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_pdhpdl import analysis, simulador, strategy  # noqa: E402
from scripts.us100_pdhpdl.run_backtest import CARPETA, OUT, cargar  # noqa: E402
from validacion import pf_inference as pi  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["us100", "nq"])
    a = ap.parse_args()
    cfg = cargar_config(CARPETA)
    if a.fuente:
        cfg["datos"]["fuente"] = a.fuente
    b = cargar(cfg)
    cen = [tuple(cfg["riesgo"]["combo_central"])]
    filas = []
    rr = cfg["rejilla_robustez"]
    variantes = [("ultima_entrada", v, dict(ultima_entrada=v)) for v in rr["ultima_entrada"]] + \
                [("rechazo_cierre", v, dict(rechazo_cierre=v)) for v in rr["rechazo_cierre"]]
    for nom, val, kw in variantes:
        sen = strategy.generar_senales(b, cfg, **kw)
        t = simulador.simular_trades(b, sen, cfg, combos=cen)
        r = pi.resumen_r(t.R.values, grupos=t.fecha.values)
        filas.append(dict(param=nom, valor=val, n=r.get("n", 0), PF=r.get("PF"), ic90_lo=r.get("pf_lo_dia"), expR=r.get("expR")))
    d = pd.DataFrame(filas)
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / f"robustez_senal_{cfg['datos']['fuente']}.csv", index=False)
    print(d.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
