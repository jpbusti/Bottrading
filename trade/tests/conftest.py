"""Fixture compartida: 5 sesiones sintéticas de velas de 5m (09:30-15:55) con indicadores calculados."""
import numpy as np
import pandas as pd
import pytest

from config import config as cfg
from src.indicadores import agregar_indicadores


@pytest.fixture(scope="session")
def df_sintetico():
    rng = np.random.default_rng(42)
    dias = pd.bdate_range("2025-01-06", periods=5)
    partes = []
    precio = 20000.0
    for d in dias:
        idx = pd.date_range(f"{d.date()} 09:30", f"{d.date()} 15:55", freq="5min", tz=cfg.ZONA_HORARIA)
        cierre = precio + np.cumsum(rng.normal(0, 8, len(idx)))
        abre = np.r_[precio, cierre[:-1]]
        alto = np.maximum(abre, cierre) + rng.uniform(0, 5, len(idx))
        bajo = np.minimum(abre, cierre) - rng.uniform(0, 5, len(idx))
        partes.append(pd.DataFrame({"Open": abre, "High": alto, "Low": bajo, "Close": cierre,
                                    "Volume": rng.integers(100, 1000, len(idx)).astype(float)}, index=idx))
        precio = cierre[-1]
    df = pd.concat(partes)
    df["Date"] = df.index.date
    return agregar_indicadores(df, cfg)
