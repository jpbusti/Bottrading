"""Robustez de parametros de US100 ORB: cambia UN parametro a la vez (config.yaml: rejilla_robustez) y reporta PF/IC90 del combo central.
Parte del backtest completo: NO ejecutar antes de cerrar el estudio de eventos (Fase 0).   Uso: python scripts/us100_orb/run_robustez.py"""
import copy
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_orb import simulador, strategy  # noqa: E402
from scripts.us100_orb.run_backtest import CARPETA, OUT, cargar  # noqa: E402
from validacion import pf_inference as pi  # noqa: E402


def main():
    cfg = cargar_config(CARPETA)
    b = cargar(cfg)
    cen = [tuple(cfg["riesgo"]["combo_central"])]
    filas = []
    for nombre, ruta, valores in (("vwap_barras", ("filtros", "vwap_pendiente", "barras"), cfg["rejilla_robustez"]["vwap_barras"]),
                                  ("retest_max_barras", ("filtros", "retest", "max_barras"), cfg["rejilla_robustez"]["retest_max_barras"]),
                                  ("ultima_entrada", ("sesion", "ultima_entrada"), cfg["rejilla_robustez"]["ultima_entrada"])):
        for v in valores:
            c = copy.deepcopy(cfg)
            d = c
            for k in ruta[:-1]:
                d = d[k]
            d[ruta[-1]] = v
            t = simulador.simular_trades(b, strategy.generar_senales(b, c), c, combos=cen)
            r = pi.resumen_r(t.R.values, grupos=t.fecha.values) if len(t) else dict(n=0)
            filas.append(dict(parametro=nombre, valor=v, n=r["n"], PF=r.get("PF"), pf_lo_dia=r.get("pf_lo_dia"), expR=r.get("expR")))
    res = pd.DataFrame(filas)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "robustez_parametros.csv", index=False)
    print(res.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
