"""us100_pdhpdl: senales (toque, rechazo, un trade por nivel) y simulacion con datos sinteticos."""
import numpy as np
import pandas as pd

from scripts._comun.config import cargar_config
from scripts.us100_pdhpdl import simulador, strategy

RAIZ = __import__("pathlib").Path(__file__).resolve().parents[1]
CFG = cargar_config(RAIZ / "scripts" / "us100_pdhpdl")


def _dia(pdh=105.0, pdl=95.0, mod=None):
    idx = pd.date_range("2024-03-12 09:30", periods=78, freq="5min")
    b = pd.DataFrame(dict(open=100.0, high=100.1, low=99.9, close=100.0, volume=1.0), index=idx)
    b["fecha"] = idx.date
    b["pdh"], b["pdl"], b["atr_d"] = pdh, pdl, 10.0
    if mod:
        mod(b)
    return b


def _set(b, i, **kw):
    for k, v in kw.items():
        b.iloc[i, b.columns.get_loc(k)] = v


def test_rechazo_en_pdh_da_corto_en_barra_siguiente():
    b = _dia(mod=lambda b: _set(b, 10, high=105.5, close=104.0))
    s = strategy.generar_senales(b, CFG)
    assert len(s) == 1 and s.d[0] == -1 and s.i_senal[0] == 10 and s.i_entrada[0] == 11


def test_cierre_mas_alla_del_nivel_no_opera_con_rechazo_pero_si_sin_el():
    b = _dia(mod=lambda b: _set(b, 10, high=106.0, close=105.5))
    assert len(strategy.generar_senales(b, CFG)) == 0
    assert len(strategy.generar_senales(b, CFG, rechazo_cierre=False)) == 1


def test_rechazo_en_pdl_da_largo_y_un_solo_trade_por_nivel():
    def mod(b):
        _set(b, 10, low=94.5, close=96.0)
        _set(b, 20, low=94.0, close=96.0)     # segundo toque: ignorado
    s = strategy.generar_senales(_dia(mod=mod), CFG)
    assert len(s) == 1 and s.d[0] == 1 and s.i_senal[0] == 10


def test_no_hay_senal_despues_de_la_ultima_entrada():
    b = _dia(mod=lambda b: _set(b, 75, high=106.0, close=104.0))   # 15:45 ET
    assert len(strategy.generar_senales(b, CFG)) == 0


def test_simular_sl_antes_que_tp_en_misma_barra_y_costo():
    O = np.full(10, 100.0)
    H = np.full(10, 100.0)
    L = np.full(10, 100.0)
    C = np.full(10, 100.0)
    H[2], L[2] = 103.0, 97.0
    r, pnl, mot = simulador.simular(H, L, C, O, 1, 9, 1, 2.0, 2.0, 0.5)
    assert mot == "SL" and pnl == -2.0 and np.isclose(r, (-2.0 - 0.5) / 2.0)
    r, pnl, mot = simulador.simular(H, L, C, O, 1, 9, -1, 2.0, 5.0, 0.0)   # corto: SL arriba (102) toca en barra 2
    assert mot == "SL"
