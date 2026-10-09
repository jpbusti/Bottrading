"""us100_orb: config coincide con el pre-registro, senales (OR, ruptura, filtros, retest), sin look-ahead y simulacion. Solo datos sinteticos."""
import ast
import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts._comun.config import cargar_config
from scripts.us100_orb import datos, simulador, strategy

RAIZ = Path(__file__).resolve().parents[1]
CFG = cargar_config(RAIZ / "scripts" / "us100_orb")
CFG3 = copy.deepcopy(CFG)
CFG3["filtros"]["vwap_pendiente"]["barras"] = 3     # las sesiones sinteticas rompen en la 4a barra


def _dias(n_dias=2, mod=None):
    """n_dias sesiones de 78 barras 5m planas en 100; `mod(dia, df)` ajusta el ultimo dia."""
    partes = []
    for k in range(n_dias):
        idx = pd.date_range(f"2024-03-{11 + k} 09:30", periods=78, freq="5min")
        df = pd.DataFrame(dict(open=100.0, high=100.1, low=99.9, close=100.0, volume=100.0), index=idx)
        df["fecha"] = idx.date
        partes.append(df)
    b = pd.concat(partes)
    b["atr_d"] = 10.0
    if mod:
        mod(b)
    return strategy.agregar_indicadores(b, CFG)


def _caso_largo(b):
    d = b.index.date == b.index.date.max()
    i = np.flatnonzero(d)
    b.iloc[i[0:3], b.columns.get_loc("high")] = 101.0
    b.iloc[i[0:3], b.columns.get_loc("low")] = 99.0
    for pos, (o, h, l, c, v) in {3: (101, 102.5, 100.9, 102, 300), 4: (102, 102.2, 100.9, 101.5, 100)}.items():
        for col, val in zip(("open", "high", "low", "close", "volume"), (o, h, l, c, v)):
            b.iloc[i[pos], b.columns.get_loc(col)] = float(val)


def test_config_coincide_con_preregistro():
    assert CFG["riesgo"]["k_sl"] == [0.8, 1.0, 1.2] and CFG["riesgo"]["m_tp"] == [1.5, 1.75, 2.0]
    assert CFG["opening_range"]["minutos"] == 15 and CFG["datos"]["timeframe_min"] == 5
    assert CFG["filtros"]["vwap_pendiente"]["barras"] == 5 and CFG["filtros"]["retest"]["max_barras"] == 6
    assert CFG["sesion"]["ultima_entrada"] == "15:00" and CFG["costos"]["slippage_pts_lado"] == 0.5
    r = CFG["rejilla_robustez"]
    assert (r["vwap_barras"], r["retest_max_barras"], r["ultima_entrada"]) == ([3, 5, 10], [4, 6, 8], ["14:30", "15:00", "15:30"])
    assert CFG["filtros"]["volumen"]["multiplo"] == 1.5 and CFG["filtros"]["volumen"]["ventana"] == 20
    assert CFG["atr"]["periodo"] == 14 and CFG["costos"]["spread_pts"]["min"] == 1.0 and CFG["costos"]["spread_pts"]["max"] == 1.5
    a = CFG["aprobacion"]
    assert (a["pf_min"], a["ic90_pf_inferior_min"], a["trades_min"], a["max_dd_pct"]) == (1.15, 1.0, 300, 20.0)


def test_pendiente_vwap_se_lee_del_config():
    assert CFG["filtros"]["vwap_pendiente"]["barras"] == 5
    assert len(strategy.generar_senales(_dias(mod=_caso_largo), CFG)) == 0     # con 5 barras la sesion sintetica no tiene historia
    assert len(strategy.generar_senales(_dias(mod=_caso_largo), CFG3)) == 1    # con 3 si: el parametro viene del config


def test_senal_larga_con_ruptura_filtros_y_retest():
    b = _dias(mod=_caso_largo)
    s = strategy.generar_senales(b, CFG3)
    assert len(s) == 1
    r = s.iloc[0]
    assert r.d == 1 and r.nivel == 101.0 and r.i_confirma == 78 + 4 and r.i_entrada == 78 + 5
    assert b.index[r.i_entrada].strftime("%H:%M") == "09:55"


def test_filtro_volumen_bloquea():
    def mod(b):
        _caso_largo(b)
        b.iloc[78 + 3, b.columns.get_loc("volume")] = 100.0
    assert len(strategy.generar_senales(_dias(mod=mod), CFG3)) == 0


def test_retest_invalido_si_cierra_dentro_del_or():
    def mod(b):
        _caso_largo(b)
        b.iloc[78 + 4, b.columns.get_loc("close")] = 100.5      # vuelve dentro del OR antes de confirmar
    assert len(strategy.generar_senales(_dias(mod=mod), CFG3)) == 0


def test_sin_retest_activo_entra_tras_la_ruptura():
    cfg = copy.deepcopy(CFG3)
    cfg["filtros"]["retest"]["activo"] = False
    s = strategy.generar_senales(_dias(mod=_caso_largo), cfg)
    assert s.iloc[0].i_confirma == 78 + 3 and s.iloc[0].i_entrada == 78 + 4


def test_sin_look_ahead_en_senal():
    b = _dias(mod=_caso_largo)
    base = strategy.generar_senales(b, CFG3)
    b2 = b.copy()
    pos = int(base.iloc[0].i_entrada)
    b2.iloc[pos + 1:, b2.columns.get_loc("high")] = 999.0          # futuro alterado tras la entrada
    b2.iloc[pos + 1:, b2.columns.get_loc("low")] = -999.0
    b2 = strategy.agregar_indicadores(b2.drop(columns=["vwap", "vol_rel"]), CFG3)
    pd.testing.assert_frame_equal(base, strategy.generar_senales(b2, CFG3))


def test_atr_diario_usa_solo_dias_previos():
    partes = [pd.date_range(f"{f} 09:30", periods=78, freq="5min") for f in pd.bdate_range("2024-03-01", periods=20)]
    idx = partes[0].append(partes[1:])
    d = pd.DataFrame(dict(open=100.0, high=101.0, low=99.0, close=100.0, volume=1.0), index=idx)
    d["fecha"] = d.index.date
    a1 = datos.atr_diario(d, 14)
    d.loc[d.fecha == d.fecha.max(), "high"] = 500.0                  # el ultimo dia no puede afectar su propio ATR
    a2 = datos.atr_diario(d, 14)
    assert a1.iloc[-1] == a2.iloc[-1]


def test_simular_tp_sl_y_tiempo():
    n = 10
    O = np.full(n, 100.0); H = np.full(n, 100.1); L = np.full(n, 99.9); C = np.full(n, 100.0)
    H[3] = 111.0
    r, pnl, mot = simulador.simular(H, L, C, O, 1, 8, 1, sl=5.0, tp=10.0, costo=2.0)
    assert mot == "TP" and r == pytest.approx((10 - 2) / 5)
    H[3], L[3] = 111.0, 90.0
    assert simulador.simular(H, L, C, O, 1, 8, 1, 5.0, 10.0, 2.0)[2] == "SL"           # SL primero si ambos en la misma barra
    H[:], L[:] = 100.1, 99.9; C[8] = 97.0
    r, pnl, mot = simulador.simular(H, L, C, O, 1, 8, -1, 50.0, 50.0, 0.0)
    assert mot == "T" and pnl == pytest.approx(3.0)


def test_costo_base_es_spread_mas_slippage():
    assert simulador.costo_pts(CFG) == pytest.approx(2.5)                 # spread 1.5 + 2 x 0.5
    assert simulador.costo_pts(CFG, spread=1.0) == pytest.approx(2.0)


def test_simular_trades_una_fila_por_combo():
    b = _dias(mod=_caso_largo)
    sen = strategy.generar_senales(b, CFG3)
    tr = simulador.simular_trades(b, sen, CFG3)
    assert len(tr) == 9 and set(tr.combo) == {(k, m) for k in (0.8, 1.0, 1.2) for m in (1.5, 1.75, 2.0)}
    tr_inv = simulador.simular_trades(b, sen, CFG3, invertir=True)
    assert (tr_inv.d == -1).all()


def test_validacion_nunca_importa_scripts():
    """Regla del estandar: la dependencia es scripts -> validacion, nunca al reves."""
    for f in (RAIZ / "validacion").glob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
            assert not any(m == "scripts" or m.startswith("scripts.") for m in mods), f"{f.name} importa scripts"
