"""Placebos sobre el combo central: nivel (PDH/PDL de hace N dias), timing aleatorio y direccion invertida.
Uso (desde trade/):  python scripts/us100_pdhpdl/run_placebo.py [--fuente us100|nq]
Salida: resultados/us100_pdhpdl/placebos_<fuente>.txt"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_pdhpdl import simulador, strategy  # noqa: E402
from scripts.us100_pdhpdl.run_backtest import CARPETA, OUT, cargar  # noqa: E402
from validacion import placebo as pl  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["us100", "nq"])
    a = ap.parse_args()
    cfg = cargar_config(CARPETA)
    if a.fuente:
        cfg["datos"]["fuente"] = a.fuente
    cen = [tuple(cfg["riesgo"]["combo_central"])]
    p = cfg["validacion"]["placebos"]
    b = cargar(cfg)
    sen = strategy.generar_senales(b, cfg)

    def serie(senales=sen, **kw):
        return simulador.simular_trades(b, senales, cfg, combos=cen, **kw).R.values

    real = serie()
    nivel = pl.placebo_nivel(real, lambda lag: serie(strategy.generar_senales(b, cfg, lag=lag)), lags=tuple(p["lags_nivel"]))
    timing = pl.placebo_timing(real, lambda s: serie(timing_rng=np.random.default_rng(s)), n=p["sorteos_timing"], alpha=p["alpha"])
    direc = pl.placebo_direccion(real, serie(invertir=True))
    ver = pl.veredicto(nivel, timing, direc)
    lineas = [f"US100 PDH/PDL {cfg['datos']['fuente']} combo {cen[0]}: n={len(real)}", f"nivel: {nivel}", f"timing: {timing}",
              f"direccion: {direc}", f"veredicto: {ver}"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"placebos_{cfg['datos']['fuente']}.txt").write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
