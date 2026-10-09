"""Controles del motor US100: simulacion de SL/TP, perfil, VWAP y sin look-ahead en ATR."""
import numpy as np
import pytest

from scripts.us100_v1 import motor_us100 as m


def _dia(o=100.0, n=390):
    a = np.full(n, o)
    return m.Dia(None, a.copy(), a.copy() + 0.1, a.copy() - 0.1, a.copy(), np.full(n, 100.0))


def test_simular_tp_largo():
    x = _dia()
    x.h[22] = 112.0                       # entrada idx 21 a 100; TP = +10 -> 110 toca en idx 22
    r, pnl, mot, entry = m.simular(x, 20, 1, sl_dist=5.0, tp_dist=10.0, costo=2.0)
    assert mot == "TP" and entry == 100.0 and r == pytest.approx((10 - 2) / 5)


def test_simular_sl_gana_si_ambos_en_la_misma_vela():
    x = _dia()
    x.h[22], x.l[22] = 115.0, 90.0
    r, pnl, mot, _ = m.simular(x, 20, 1, 5.0, 10.0, costo=2.0)
    assert mot == "SL" and r == pytest.approx((-5 - 2) / 5)


def test_simular_corto_y_salida_por_tiempo():
    x = _dia()
    x.c[m.FIN_VENTANA] = 97.0             # corto, no toca nada: sale al cierre de 11:59 con +3
    r, pnl, mot, _ = m.simular(x, 20, -1, 50.0, 50.0, costo=0.0)
    assert mot == "T" and pnl == pytest.approx(3.0) and r == pytest.approx(3.0 / 50)


def test_no_entra_fuera_de_ventana():
    x = _dia()
    assert m.simular(x, 120, 1, 5.0, 5.0) is None        # entrada seria idx 121 (> 11:30)


def test_perfil_poc_y_area_de_valor():
    x = _dia()
    x.h[:], x.l[:] = 110.0, 90.0
    x.h[:100], x.l[:100] = 101.0, 99.0                   # el volumen se concentra cerca de 100
    poc, vah, val = m._perfil(x)
    assert 98 <= poc <= 102 and val < poc < vah and vah - val < 20


def test_vwap_constante_si_precio_constante():
    x = _dia()
    assert np.allclose(m._vwap(x), 100.0, atol=1e-9)


def test_costo_base_es_2_puntos_y_estres_3():
    assert m.COSTO_BASE == pytest.approx(2.0) and m.COSTO_ESTRES == pytest.approx(3.0)
