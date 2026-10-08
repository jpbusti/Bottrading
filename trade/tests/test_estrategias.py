import pandas as pd
import pytest

from src.estrategias import (Senal, Estrategia, EstrategiaPDH_PDL, EstrategiaORB, EstrategiaVWAP,
                             crear_filtros, aplicar_filtro)
from src.motor.motor_estrategias import DatosPreparados, backtest_estrategia, params_tp_fijo

ESTRATEGIAS = [EstrategiaPDH_PDL(), EstrategiaORB(), EstrategiaVWAP(), EstrategiaVWAP(invertir=True)]


@pytest.mark.parametrize("est", ESTRATEGIAS, ids=lambda e: e.nombre)
def test_formato_senales(df_sintetico, est):
    assert isinstance(est, Estrategia)
    senales = est.generar_senales(df_sintetico)
    assert isinstance(senales, list)
    for s in senales:
        assert isinstance(s, Senal)
        assert isinstance(s.ts, pd.Timestamp) and s.ts in df_sintetico.index
        assert s.direccion in (1, -1)
        assert s.precio == pytest.approx(df_sintetico.loc[s.ts, "Close"])
    tiempos = [s.ts for s in senales]
    assert tiempos == sorted(tiempos)


def test_vwap_inv_es_el_espejo(df_sintetico):
    a = EstrategiaVWAP().generar_senales(df_sintetico)
    b = EstrategiaVWAP(invertir=True).generar_senales(df_sintetico)
    assert len(a) == len(b) > 0
    assert [s.ts for s in a] == [s.ts for s in b]
    assert all(x.direccion == -y.direccion for x, y in zip(a, b))


def test_orb_una_ruptura_por_lado_y_dia(df_sintetico):
    senales = EstrategiaORB().generar_senales(df_sintetico)
    claves = [(s.ts.date(), s.direccion) for s in senales]
    assert len(claves) == len(set(claves))
    # nunca dentro de los primeros 30 min (09:30-09:55)
    assert all(s.ts.hour * 60 + s.ts.minute >= 10 * 60 for s in senales)


def test_pdh_pdl_direccion_correcta(df_sintetico):
    for s in EstrategiaPDH_PDL().generar_senales(df_sintetico):
        fila = df_sintetico.loc[s.ts]
        if s.direccion == -1:
            assert fila["High"] >= fila["PDH"] * 0.999
        else:
            assert fila["Low"] <= fila["PDL"] * 1.001


def test_filtros_reducen_senales(df_sintetico):
    senales = EstrategiaVWAP().generar_senales(df_sintetico)
    for f in crear_filtros():
        filtradas = aplicar_filtro(df_sintetico, senales, f)
        assert len(filtradas) <= len(senales)
        if f.nombre == "sin_filtro":
            assert len(filtradas) == len(senales)


def test_backtest_corre_de_punta_a_punta(df_sintetico):
    prep = DatosPreparados(df_sintetico, "5m")
    p = params_tp_fijo(40, 40, 2, "15:00")
    trades, m = backtest_estrategia(prep, EstrategiaVWAP(), p)
    assert m is not None and m["Total_Trades"] == len(trades) > 0
    assert 0 <= m["Win_Rate"] <= 100
