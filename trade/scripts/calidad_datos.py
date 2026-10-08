"""Reporte de calidad de velas 1m RTH (Databento). Uso: python scripts/calidad_datos.py <csv|csv.gz> <salida.txt> [desde] [hasta]
Mismos chequeos que data/raw/calidad/reporte_calidad_validacion.txt (duplicados, sesiones cortas, huecos, OHLC, rolls)."""
import sys
import pandas as pd

ruta, salida = sys.argv[1], sys.argv[2]
desde = sys.argv[3] if len(sys.argv) > 3 else None
hasta = sys.argv[4] if len(sys.argv) > 4 else None
d = pd.read_csv(ruta)
d["Datetime"] = pd.to_datetime(d["Datetime"], utc=True).dt.tz_convert("America/New_York")
d["fecha"] = d["Datetime"].dt.date
if desde:
    d = d[d["fecha"] >= pd.Timestamp(desde).date()]
if hasta:
    d = d[d["fecha"] <= pd.Timestamp(hasta).date()]
d = d.sort_values("Datetime").reset_index(drop=True)
ses = d.groupby("fecha").size()
gap = d["Datetime"].diff().dt.total_seconds().div(60)
mismo = d["fecha"].eq(d["fecha"].shift())
rango = (d["High"] - d["Low"]) / d["Close"]
inco = ((d["High"] < d[["Open", "Close", "Low"]].max(axis=1)) | (d["Low"] > d[["Open", "Close", "High"]].min(axis=1))).sum()
L = [f"=== {ruta} ({desde or 'inicio'} -> {hasta or 'fin'}) ===",
     f"Velas: {len(d):,} | Sesiones: {len(ses):,} | {d['Datetime'].iloc[0]} -> {d['Datetime'].iloc[-1]}",
     f"Timestamps duplicados: {int(d['Datetime'].duplicated().sum())}",
     f"Sesiones con <350 velas (de 390): {int((ses < 350).sum())} | con <200: {int((ses < 200).sum())}",
     "Sesiones por anio: " + ", ".join(f"{k}:{v}" for k, v in pd.Series(ses.index).map(lambda x: x.year).value_counts().sort_index().items()),
     f"Huecos intradia >5 min: {int(((gap > 5) & mismo).sum())} | >30 min: {int(((gap > 30) & mismo).sum())}",
     f"Velas con rango >1%: {int((rango > 0.01).sum())} | >3%: {int((rango > 0.03).sum())}",
     f"Velas con OHLC incoherente: {int(inco)} | precios <=0: {int((d[['Open','High','Low','Close']] <= 0).any(axis=1).sum())}"]
if len(sys.argv) <= 5:
    open(salida, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
