#!/usr/bin/env python3
"""
Descarga datos históricos de Databento para NQ futuros
Múltiples timeframes: 5m, 15m, 30m, 1h
"""

import subprocess
import sys

# Instalar databento si no está
try:
    import databento as db
except ImportError:
    print("📦 Instalando databento...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "databento", "-q"])
    import databento as db

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Tu API key
API_KEY = "db-36w98AFLXsuwYNgv5Ai6TfQFdKbbh"

# Timeframes a descargar
TIMEFRAMES = ["5m", "15m", "30m", "1h"]

# Período: últimos 12 meses
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=365)

print(f"📅 Descargando desde {START_DATE.date()} hasta {END_DATE.date()}")
print(f"📊 Timeframes: {', '.join(TIMEFRAMES)}")

# Carpeta relativa al script
script_dir = Path(__file__).parent
raw_dir = script_dir / "data" / "raw"
raw_dir.mkdir(parents=True, exist_ok=True)

try:
    client = db.Historical(api_key=API_KEY)

    for tf in TIMEFRAMES:
        print(f"\n📥 Descargando NQ en {tf}...")

        try:
            data = client.timeseries.get_range(
                dataset="XNAS",
                symbols="NQ.FUT.CBE",
                start=START_DATE.strftime("%Y-%m-%d"),
                end=END_DATE.strftime("%Y-%m-%d"),
                schema="ohlcv",
                stype_in="continuous_contract",
                resolution=tf
            )

            if hasattr(data, 'to_pandas'):
                df = data.to_pandas()
            else:
                df = pd.DataFrame(data)

            filename = raw_dir / f"NQ_databento_{tf}.csv"
            df.to_csv(filename, index=False)

            print(f"   ✅ Guardado: {filename}")
            print(f"   📊 Registros: {len(df)}")

        except Exception as e:
            print(f"   ❌ Error en {tf}: {e}")

    print("\n" + "="*60)
    print("✅ DESCARGA COMPLETADA")
    print("="*60)
    print("\n📂 Archivos descargados:")
    for file in sorted(raw_dir.glob("NQ_databento_*.csv")):
        size_mb = file.stat().st_size / 1024 / 1024
        print(f"   ✓ {file.name} ({size_mb:.1f} MB)")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("Verifica tu API key en https://databento.com/account/api")
