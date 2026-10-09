"""Placebos de US100 ORB sobre el combo central: nivel (OR de otros dias), timing aleatorio y direccion invertida.
NO ejecutar hasta firmar docs/PREREGISTRO_US100_ORB.md.   Uso: python scripts/us100_orb/run_placebo.py [--fuente us100|nq]
Salida: resultados/us100_orb/placebos_<fuente>.txt"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_orb import simulador, strategy  # noqa: E402
from scripts.us100_orb.run_backtest import CARPETA, OUT, cargar  # noqa: E402
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
        t = simulador.simular_trades(b, senales, cfg, combos=cen, **kw)
        return t.R.values

    real = serie()
    nivel = pl.placebo_nivel(real, lambda lag: serie(strategy.generar_senales(b, cfg, lag_or=lag)), lags=tuple(p["lags_nivel"]))
    timing = pl.placebo_timing(real, lambda s: serie(timing_rng=np.random.default_rng(s)), n=p["sorteos_timing"], alpha=p["alpha"])
    direc = pl.placebo_direccion(real, serie(invertir=True))
    ver = pl.veredicto(nivel, timing, direc)
    lineas = [f"US100 ORB {cfg['datos']['fuente']} combo {cen[0]}: n={len(real)}", f"nivel: {nivel}", f"timing: {timing}",
              f"direccion: {direc}", f"veredicto: {ver}"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"placebos_{cfg['datos']['fuente']}.txt").write_text("\n".join(lineas), encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
