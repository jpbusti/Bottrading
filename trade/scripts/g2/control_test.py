"""Control del motor: debe reproducir n=172, PF 1.629 del script original (NQ 1 anio, VWAP, SL80/TP110, costo 3)."""
import logging, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_g2 as m
logging.basicConfig(level=logging.INFO, format="%(message)s")
RUTA = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "raw" / "nq" / "NQ_databento_1m.csv"
raw = pd.read_csv(RUTA)
raw["Datetime"] = pd.to_datetime(raw["Datetime"], utc=True).dt.tz_convert(m.NY)
raw = raw.sort_values("Datetime").drop_duplicates("Datetime")
mm = raw.Datetime.dt.hour*60 + raw.Datetime.dt.minute
raw = raw[(mm>=570)&(mm<960)].copy()
raw["fecha"] = raw.Datetime.dt.date; raw["symbol"]="X"
M = m.Mercado(raw, "NQ_control")
# 1) filtro VWAP solo, sin hora ni POC (equivale a fila VWAP SL80/TP110 del script original)
t = M.correr("FIJO", lag=1, usar_hora=False, sin_poc=False, warm=1)
r = m.resumen(t, 3.0)
print("CONTROL VWAP 80/110 cost3:", {k: round(v,3) for k,v in r.items()})
print("original:   n=172 win=54.07 PF=1.63 pts_por_trade=21.51")
# 2) con filtros hora/POC en modo pre y post
for modo in ["pre","post"]:
    t2 = M.correr("FIJO", lag=1, modo_filtro=modo, warm=1)
    r2 = m.resumen(t2, 3.0)
    print(modo, {k: round(v,3) for k,v in r2.items()})
