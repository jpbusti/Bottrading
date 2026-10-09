"""Tests de integridad de los datasets reconstruidos/limpios."""
import gzip
from pathlib import Path

import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
NQ_FM = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth.csv.gz"
ES_FM = BASE / "data/raw/es/ES_1m_RTH_frontmonth.csv.gz"
USTEC = BASE / "data/raw/us100/USTEC_1m_clean_2018_2026.csv"


def _load_nq():
    with gzip.open(NQ_FM, "rt") as f:
        df = pd.read_csv(f)
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
    return df


def _load_es():
    with gzip.open(ES_FM, "rt") as f:
        df = pd.read_csv(f)
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
    return df


def _load_ustec():
    return pd.read_csv(USTEC, parse_dates=["Datetime"])


# ----------- NQ front-month ---------------------------------------------------

@pytest.mark.skipif(not NQ_FM.exists(), reason="NQ front-month no generado")
def test_nq_frontmonth_solo_rth():
    df = _load_nq()
    t = df["Datetime"].dt.tz_convert("America/New_York").dt.time
    assert t.min() >= pd.Timestamp("09:30").time()
    assert t.max() <= pd.Timestamp("15:59").time()


@pytest.mark.skipif(not NQ_FM.exists(), reason="NQ front-month no generado")
def test_nq_frontmonth_cobertura():
    df = _load_nq()
    anios = df["Datetime"].dt.year.unique()
    assert 2016 in anios and 2021 in anios


@pytest.mark.skipif(not NQ_FM.exists(), reason="NQ front-month no generado")
def test_nq_frontmonth_saltos_roll_razonables():
    """Los saltos de precio en rolls deben ser <200 pts (basis normal, no errores)."""
    df = _load_nq()
    df = df.sort_values("Datetime")
    # Detectar dias de roll: cambio de Symbol
    fechas = df["Datetime"].dt.date
    df_day = df.copy()
    df_day["fecha"] = fechas
    simbolos_por_dia = df_day.groupby("fecha")["Symbol"].first()
    rolls = [(simbolos_por_dia.index[i], simbolos_por_dia.iloc[i - 1], simbolos_por_dia.iloc[i])
             for i in range(1, len(simbolos_por_dia))
             if simbolos_por_dia.iloc[i] != simbolos_por_dia.iloc[i - 1]]
    for fecha, _, _ in rolls:
        from datetime import timedelta
        dia_ant = fecha - timedelta(days=1)
        ayer = df_day[df_day["fecha"] == dia_ant]
        hoy = df_day[df_day["fecha"] == fecha]
        if len(ayer) and len(hoy):
            salto = abs(hoy["Open"].iloc[0] - ayer["Close"].iloc[-1])
            assert salto < 200, f"Salto {salto:.2f} pts en roll {fecha} mayor a 200 pts"


# ----------- ES front-month ---------------------------------------------------

@pytest.mark.skipif(not ES_FM.exists(), reason="ES front-month no generado")
def test_es_frontmonth_solo_rth():
    df = _load_es()
    t = df["Datetime"].dt.tz_convert("America/New_York").dt.time
    assert t.min() >= pd.Timestamp("09:30").time()
    assert t.max() <= pd.Timestamp("15:59").time()


@pytest.mark.skipif(not ES_FM.exists(), reason="ES front-month no generado")
def test_es_frontmonth_cobertura_2016_2026():
    df = _load_es()
    anios = df["Datetime"].dt.year.unique()
    assert 2016 in anios and 2026 in anios


@pytest.mark.skipif(not ES_FM.exists(), reason="ES front-month no generado")
def test_es_frontmonth_sin_spreads_roll():
    """No debe haber filas con '-' en Symbol (spreads de roll filtrados)."""
    df = _load_es()
    assert not df["Symbol"].str.contains("-", na=False).any()


# ----------- USTEC limpio -----------------------------------------------------

@pytest.mark.skipif(not USTEC.exists(), reason="USTEC clean no generado")
def test_ustec_no_pre2018():
    df = _load_ustec()
    anios = df["Datetime"].dt.year
    assert anios.min() >= 2018, f"Hay datos de {anios.min()}, esperado >= 2018"


@pytest.mark.skipif(not USTEC.exists(), reason="USTEC clean no generado")
def test_ustec_spread_pts_medio_razonable():
    """Spread medio IC Markets US100 debe estar entre 1.0 y 2.5 pts."""
    df = _load_ustec()
    media = df["Spread_pts"].mean()
    assert 1.0 <= media <= 2.5, f"Spread medio {media:.3f} fuera de rango esperado 1.0-2.5"


@pytest.mark.skipif(not USTEC.exists(), reason="USTEC clean no generado")
def test_ustec_spread_pts_son_puntos_no_enteros():
    """Verificar que spread ya esta dividido por 100 (valores ~1.0-3.0, no ~100-300)."""
    df = _load_ustec()
    assert df["Spread_pts"].max() < 50, "Spread parece estar en enteros, no en puntos (max > 50)"
    # Algunos bars tienen spread=0 (fuera de horario); el 90p debe estar en rango de puntos
    assert df["Spread_pts"].quantile(0.10) >= 0.5, "Percentil 10 del spread < 0.5 pts"


@pytest.mark.skipif(not USTEC.exists(), reason="USTEC clean no generado")
def test_ustec_columnas_esperadas():
    df = _load_ustec()
    for col in ["Datetime", "Open", "High", "Low", "Close", "TickVolume", "Spread_pts", "RealVolume"]:
        assert col in df.columns, f"Columna {col} faltante"


NQ_V2 = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth_10y_v2.csv.gz"


@pytest.mark.skipif(not NQ_V2.exists(), reason="NQ 10y v2 no generado")
def test_nq_10y_v2_completo_y_sin_huecos():
    with gzip.open(NQ_V2, "rt") as f:
        df = pd.read_csv(f)
    dt = pd.to_datetime(df["Datetime"], utc=True).dt.tz_convert("America/New_York")
    assert dt.dt.date.nunique() == 2577
    gap = dt.sort_values().groupby(dt.dt.date).diff().dt.total_seconds() / 60
    assert gap.max() <= 15   # 4 dias de marzo 2020 con huecos de 14-15 min (volatilidad COVID)
    assert (gap > 5).sum() <= 4
