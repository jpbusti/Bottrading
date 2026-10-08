"""Control negativo LSR v1: placebos de nivel (D-N), direccion invertida y timing aleatorio (combo central 1.0/1.75).
Uso: python run_placebos.py <carpeta_pkl> <carpeta_salida> [instrumento=NQ] [n_timing=30]
No es una estrategia nueva: re-evalua LSR v1 ya rechazada para comprobar que el pipeline comun reproduce el rechazo."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_lsr as m
from validacion import placebo as pl

PKL, OUT = Path(sys.argv[1]), Path(sys.argv[2])
INST = sys.argv[3] if len(sys.argv) > 3 else "NQ"
NT = int(sys.argv[4]) if len(sys.argv) > 4 else 30
OUT.mkdir(parents=True, exist_ok=True)
CEN = (1.0, 1.75)

M = m.Mercado(pd.read_pickle(PKL / f"{INST}_contratos_ext.pkl"), INST)


def serie(**kw):
    d = m.generar(M, "A", grid=False, extra_ks=(CEN,), **kw)
    return m.Rnet(d[d.combo == CEN]) if len(d) else np.array([])


real = serie()
nivel = pl.placebo_nivel(real, lambda lag: serie(lag=lag), lags=(2, 3, 5))
direc = pl.placebo_direccion(real, serie(invertir=True))
timing = pl.placebo_timing(real, lambda s: serie(timing_rng=np.random.default_rng(s)), n=NT)
ver = pl.veredicto(nivel, timing, direc)

lineas = [f"LSR v1 {INST} bloque A, combo {CEN}: n={len(real)} PF_neto={m.pf(real):.3f}",
          f"Placebo nivel D-N: {nivel}", f"Placebo direccion invertida: {direc}",
          f"Placebo timing aleatorio ({NT} sorteos): {timing}", f"Veredicto placebos: {ver}"]
(OUT / f"placebos_{INST}.txt").write_text("\n".join(lineas), encoding="utf-8")
print("\n".join(lineas))
