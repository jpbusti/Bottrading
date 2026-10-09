"""Reconstruir serie NQ 1m RTH front-month desde el archivo ZST crudo (Databento multi-contrato).

Algoritmo: para cada dia de trading, seleccionar el contrato con mayor volumen total
(front-month natural). El resultado no tiene saltos de precio en los rolls porque
usamos el precio real de cada contrato, no un continuo pegado.

Cobertura del ZST: 2016-10-09 a 2021-10-08. Para 2021-2026, ver nota al final del script.

Uso: python scripts/descarga/reconstruir_frontmonth_nq.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import zstandard as zstd

BASE = Path(__file__).resolve().parents[2]
ZST = BASE / "data/raw/databento_crudo/NQ_databento_1m_2016_2021_RTH.csv.zst"
OUT = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth.csv.gz"

# RTH en UTC: 09:30-16:00 ET
# ET invierno = UTC-5 -> RTH = 14:30-21:00 UTC
# ET verano   = UTC-4 -> RTH = 13:30-20:00 UTC
# El ZST ya esta filtrado a RTH aprox (confirmado por auditoria); usamos la ventana amplia 13:00-21:00 UTC y
# luego filtramos por horario exacto con pandas.
RTH_START_UTC_H = 13   # 09:00 ET invierno (UTC-5) = 14:00 UTC; usamos 13 para coger ambas epocas DST
RTH_END_UTC_H = 21


def main():
    print(f"Leyendo {ZST} ...")
    with open(ZST, "rb") as f:
        dctx = zstd.ZstdDecompressor()
        reader = dctx.stream_reader(f)
        raw = io.TextIOWrapper(reader, encoding="utf-8")
        df = pd.read_csv(raw)

    print(f"  Filas crudas: {len(df):,}")
    print(f"  Columnas: {list(df.columns)}")
    print(f"  Contratos presentes: {sorted(df['symbol'].unique())[:10]} ...")

    # Parsear timestamp UTC
    df["ts"] = pd.to_datetime(df["ts_event"], utc=True)

    # Filtrar solo RTH (13:00-21:00 UTC cubre ambas epocas DST)
    h = df["ts"].dt.hour
    df = df[(h >= RTH_START_UTC_H) & (h < RTH_END_UTC_H)].copy()
    print(f"  Filas tras filtro horario RTH: {len(df):,}")

    # Fecha de trading
    df["fecha"] = df["ts"].dt.date

    # Por dia, seleccionar el contrato con mayor volumen total = front-month
    vol_dia = df.groupby(["fecha", "symbol"])["volume"].sum()
    fm = vol_dia.groupby(level="fecha").idxmax().apply(lambda x: x[1])  # fecha -> symbol
    print(f"  Dias de trading: {len(fm)}")

    # Estadisticas de rolls (cambio de contrato dia a dia)
    symbols_por_dia = fm.values
    rolls = [(fm.index[i], symbols_por_dia[i - 1], symbols_por_dia[i])
             for i in range(1, len(symbols_por_dia)) if symbols_por_dia[i] != symbols_por_dia[i - 1]]
    print(f"  Rolls detectados: {len(rolls)}")
    for fecha, antes, despues in rolls:
        print(f"    {fecha}: {antes} -> {despues}")

    # Filtrar solo el front-month de cada dia
    df["fm"] = df["fecha"].map(fm)
    df_fm = df[df["symbol"] == df["fm"]].copy()
    print(f"  Filas front-month: {len(df_fm):,}")

    # Verificar saltos de precio en rolls
    df_fm = df_fm.sort_values("ts").reset_index(drop=True)
    for fecha, _, despues in rolls:
        dia_ant = pd.Timestamp(fecha) - pd.Timedelta(days=1)
        # ultimas barras del dia anterior
        ayer = df_fm[df_fm["fecha"] == dia_ant.date()]
        hoy = df_fm[df_fm["fecha"] == fecha]
        if len(ayer) and len(hoy):
            cierre_ayer = ayer.iloc[-1]["close"]
            apertura_hoy = hoy.iloc[0]["open"]
            salto = apertura_hoy - cierre_ayer
            print(f"    Salto precio en roll {fecha}: cierre_ayer={cierre_ayer:.2f} apertura_hoy={apertura_hoy:.2f} "
                  f"diff={salto:+.2f} pts")

    # Construir DataFrame de salida
    out = df_fm[["ts", "open", "high", "low", "close", "volume", "symbol"]].copy()
    out.columns = ["Datetime", "Open", "High", "Low", "Close", "Volume", "Symbol"]
    out["Datetime"] = out["Datetime"].dt.tz_convert("America/New_York")
    # Filtrar exactamente RTH: 09:30-16:00 ET (eliminar barras pre-open)
    t = out["Datetime"].dt.time
    out = out[(t >= pd.Timestamp("09:30").time()) & (t <= pd.Timestamp("15:59").time())].copy()

    # Guardar
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, compression="gzip")
    print(f"\nGuardado: {OUT}")
    print(f"  Filas: {len(out):,} | Dias: {out['Datetime'].dt.date.nunique()} | "
          f"Rango: {out['Datetime'].min()} -> {out['Datetime'].max()}")

    print("""
NOTA: el ZST crudo NQ solo cubre 2016-2021.
Para completar 2021-2026 necesitas descargar desde Databento:
  from databento import Historical
  client = Historical()  # requiere DATABENTO_API_KEY en variable de entorno
  data = client.timeseries.get_range(
      dataset="GLBX.MDP3",
      symbols=["NQ.FUT"],          # front-month continuo o lista de contratos trimestrales
      schema="ohlcv-1m",
      start="2021-10-09",
      end="2026-10-07",
      stype_in="continuous",       # o "raw_symbol" para multi-contrato como el ZST existente
  )
  data.to_csv("data/raw/databento_crudo/NQ_databento_1m_2021_2026_RTH.csv.zst")
Costo estimado Databento: ~$0.02-0.05 USD por dia de datos de futuros CME en schema ohlcv-1m.
5 anios (~1250 dias x 390 barras/dia) = ~$12-60 segun plan. Verificar en tu dashboard de Databento.
""")


if __name__ == "__main__":
    main()
