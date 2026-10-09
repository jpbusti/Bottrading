"""Reproduce G2 (control, ultimo anio NQ) y LSR v1 (combo central) con datos nuevos y con costo CFD 2.0 pts RT.
No es un backtest nuevo: reusa los motores congelados. Uso: python scripts/verificacion/reproducir_g2_lsr.py"""
import sys, logging
from pathlib import Path
import numpy as np, pandas as pd
R = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(R), str(R / "scripts/g2")]
import motor_g2 as g
logging.basicConfig(level=logging.WARNING)

def g2(ruta, desde=None):
    raw = pd.read_csv(ruta); raw["Datetime"] = pd.to_datetime(raw["Datetime"], utc=True).dt.tz_convert(g.NY)
    raw = raw.sort_values("Datetime").drop_duplicates("Datetime")
    if desde: raw = raw[raw.Datetime.dt.date >= pd.Timestamp(desde).date()]
    mm = raw.Datetime.dt.hour * 60 + raw.Datetime.dt.minute
    raw = raw[(mm >= 570) & (mm < 960)].copy(); raw["fecha"] = raw.Datetime.dt.date; raw["symbol"] = "X"
    M = g.Mercado(raw, "NQ"); t = M.correr("FIJO", lag=1, usar_hora=False, sin_poc=False, warm=1)
    return {c: {k: round(v, 3) for k, v in g.resumen(t, c).items() if k in ("n", "PF", "pf_lo", "pf_hi", "pts_trade")} for c in (3.0, 2.0)}

print("G2 original   (NQ_databento_1m.csv)            ", g2(R / "data/raw/nq/NQ_databento_1m.csv"))
print("G2 v2 nuevo   (10y_v2, ultimo anio 2025-10-07+)", g2(R / "data/raw/nq/NQ_1m_RTH_frontmonth_10y_v2.csv.gz", "2025-10-07"))
print("G2 v2 nuevo   (10y_v2, 10 anios completos)     ", g2(R / "data/raw/nq/NQ_1m_RTH_frontmonth_10y_v2.csv.gz"))

sys.path.insert(0, str(R / "scripts/lsr")); sys.modules.pop("motor_g2", None)
import motor_lsr as m
for inst in ("NQ", "ES"):
    M = m.Mercado(pd.read_pickle(R / f"data/processed/{inst}_contratos_ext.pkl"), inst)
    A = m.generar(M, "A"); c = A[A.combo == (1.0, 1.75)].copy()
    for et, costo in (("costo LSR congelado", None), ("CFD 2.0 pts RT", 2.0)):
        d = c.copy()
        if costo is not None: d["costo"] = costo
        r = m.resumen(d, m.MULT[inst])
        print(f"LSR v1 {inst} central 1.0/1.75 n={r['n']} [{et}] PF_bruto={r['PF_bruto']:.3f} PF_neto={r['PF_neto']:.3f} IC90=[{r['PF_lo90']:.3f},{r['PF_hi90']:.3f}]")
