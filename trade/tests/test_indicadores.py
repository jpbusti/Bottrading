import numpy as np

from src.indicadores import atr, rsi, vwap_diario, bollinger

COLUMNAS = ["ATR", "ATR_ratio", "VWAP", "RSI", "BB_mid", "BB_up", "BB_low", "BB_pctb", "PDH", "PDL"]


def test_columnas_presentes(df_sintetico):
    for c in COLUMNAS:
        assert c in df_sintetico.columns


def test_atr_positivo(df_sintetico):
    a = df_sintetico["ATR"].dropna()
    assert len(a) > 0 and (a > 0).all()
    # velas de ~10-25 puntos de rango: el ATR debe estar en un orden de magnitud razonable
    assert 1 < a.median() < 100


def test_rsi_en_rango(df_sintetico):
    r = df_sintetico["RSI"].dropna()
    assert len(r) > 0 and r.between(0, 100).all()


def test_rsi_extremos(df_sintetico):
    sube = df_sintetico["Close"].copy()
    sube[:] = np.arange(len(sube), dtype=float)   # solo subidas -> RSI 100
    assert rsi(sube, 14).dropna().iloc[-1] == 100


def test_vwap_dentro_del_rango_diario(df_sintetico):
    g = df_sintetico.groupby("Date")
    v = df_sintetico["VWAP"]
    assert v.notna().all()
    assert (v <= g["High"].transform("max") + 1e-9).all()
    assert (v >= g["Low"].transform("min") - 1e-9).all()


def test_vwap_primera_vela_es_precio_tipico(df_sintetico):
    primera = df_sintetico.groupby("Date").head(1)
    tipico = (primera["High"] + primera["Low"] + primera["Close"]) / 3
    assert np.allclose(primera["VWAP"], tipico)


def test_bollinger_ordenadas(df_sintetico):
    d = df_sintetico.dropna(subset=["BB_up", "BB_low"])
    assert (d["BB_up"] >= d["BB_mid"]).all() and (d["BB_mid"] >= d["BB_low"]).all()


def test_pdh_pdl_es_del_dia_anterior(df_sintetico):
    diario = df_sintetico.groupby("Date").agg(H=("High", "max"), L=("Low", "min"))
    fechas = list(diario.index)
    primer_dia = df_sintetico[df_sintetico["Date"] == fechas[0]]
    assert primer_dia["PDH"].isna().all()                 # sin día previo
    segundo = df_sintetico[df_sintetico["Date"] == fechas[1]]
    assert (segundo["PDH"] == diario.loc[fechas[0], "H"]).all()
    assert (segundo["PDL"] == diario.loc[fechas[0], "L"]).all()


def test_funciones_sueltas_no_fallan(df_sintetico):
    assert len(atr(df_sintetico, 14)) == len(df_sintetico)
    assert len(vwap_diario(df_sintetico)) == len(df_sintetico)
    assert len(bollinger(df_sintetico["Close"])) == 4
