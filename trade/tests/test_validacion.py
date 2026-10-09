"""Tests del modulo comun de validacion.

1) Control negativo: LSR v1 (ya RECHAZADA) debe seguir saliendo rechazada con los numeros del log resultados/lsr/resultado_lsr.log.
2) Senal aleatoria: sin edge, el PF neto de costos no puede superar ~1.
3) Bootstrap por bloques/por dia vs iid.
Los numeros de referencia son los del LOG REAL del proyecto (NQ bloque A, combo central (1.0, 1.75)).
"""
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))   # permite `python tests/<archivo>.py` desde cualquier carpeta
import ast
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from validacion import (TABLA_LSR_V1, bootstrap_bloques, bootstrap_iid, costo_pts, costo_trade, estado_verificacion,
                        excluir_cada_anio, p_valor, pf, placebo_direccion, rejilla, walk_forward)

RAIZ = Path(__file__).resolve().parents[1]
TRADES_NQ_A = RAIZ / "resultados" / "lsr" / "trades_NQ_A.csv"


def _motor_lsr():
    spec = importlib.util.spec_from_file_location("motor_lsr", RAIZ / "scripts" / "lsr" / "motor_lsr.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["motor_lsr"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lsr_nq():
    if not TRADES_NQ_A.exists():
        pytest.skip("falta resultados/lsr/trades_NQ_A.csv")
    m = _motor_lsr()
    d = pd.read_csv(TRADES_NQ_A)
    d["combo"] = d["combo"].map(ast.literal_eval)
    d["fecha"] = pd.to_datetime(d["fecha"]).dt.date
    return m, d


# ------------------------------------------------------------- 1) control negativo LSR v1
def test_control_negativo_lsr_central(lsr_nq):
    m, d = lsr_nq
    c = d[d.combo == (1.0, 1.75)]
    r = m.Rnet(c)
    lo, _, _ = m.boot_pf(r)
    assert len(c) == 1122
    assert pf(r) == pytest.approx(0.998, abs=0.002)
    assert lo == pytest.approx(0.874, abs=0.003)      # IC90 inferior < 1.0 -> no pasa
    assert lo < 1.0


def test_control_negativo_lsr_walkforward(lsr_nq):
    m, d = lsr_nq
    oos, folds = m.walk_forward(d)
    r = m.Rnet(oos)
    lo, _, _ = m.boot_pf(r)
    assert len(oos) == 901 and len(folds) == 8
    assert pf(r) == pytest.approx(1.016, abs=0.003)
    assert lo == pytest.approx(0.877, abs=0.003)
    assert pf(r) < 1.15 and lo < 1.0                  # criterios de aprobacion NO cumplidos
    assert (folds.PF_test < 1.0).sum() >= 4           # 2019, 2022, 2024 y 2026 pierden


def test_walkforward_modulo_igual_al_motor(lsr_nq):
    m, d = lsr_nq
    oos_a, _ = m.walk_forward(d)
    oos_b, _ = walk_forward(d, m.Rnet, combo_ref=m.REF)
    assert len(oos_a) == len(oos_b) and pf(m.Rnet(oos_a)) == pf(m.Rnet(oos_b))


def test_rejilla_lsr_no_robusta(lsr_nq):
    m, d = lsr_nq
    res = rejilla(d, m.Rnet)
    assert res["n_puntos"] == 9 and res["n_pf_ok"] == 0 and res["robusta"] is False
    sin = excluir_cada_anio(d[d.combo == (1.0, 1.75)], m.Rnet)
    assert len(sin) == d.anio.nunique() and sin.PF.notna().all()


def test_placebo_nivel_d2_nq_requiere_pkl():
    """Reproduccion completa del placebo D-2 (PF 1.085 > real 0.998): lento, necesita data/processed/lsr/*.pkl."""
    pkl = RAIZ / "data" / "processed" / "lsr" / "NQ_contratos_ext.pkl"
    if not pkl.exists():
        pytest.skip("falta el pkl de contratos (regenerar con scripts/lsr/extraer_contratos_ext.py + unir_nq.py)")
    m = _motor_lsr()
    M = m.Mercado(pd.read_pickle(pkl), "NQ")
    cen = (1.0, 1.75)
    d = m.generar(M, "A", lag=2, grid=False, extra_ks=(cen,))
    r = m.Rnet(d[d.combo == cen])
    assert len(r) == 795
    assert pf(r) == pytest.approx(1.085, abs=0.003)
    assert pf(r) > 0.998                               # el placebo iguala/supera a la estrategia real


# ------------------------------------------------------------- 2) senal aleatoria
def test_senal_aleatoria_pf_neto_cerca_de_1():
    """Entradas sin edge: gana TP (1.75R) con prob 1/2.75 (esperanza bruta 0). Con costo 0.05R el PF neto no supera ~1."""
    rng = np.random.default_rng(123)
    n = 40_000
    gana = rng.random(n) < 1 / 2.75
    bruto = np.where(gana, 1.75, -1.0)
    neto = bruto - 0.05
    assert 0.95 <= pf(bruto) <= 1.05                   # sin costos tambien ~1
    assert pf(neto) < 1.02
    assert pf(neto) > 0.90
    lo = bootstrap_iid(neto, n=2000)["pf_lo"]
    assert lo < 1.0                                    # un IC90 inferior > 1 aqui seria un falso positivo


def test_placebo_direccion_logica():
    rng = np.random.default_rng(1)
    real = rng.normal(0.0, 1, 500)
    assert placebo_direccion(real, real.copy())["supera"] is False
    assert p_valor(1.5, [1.0, 1.1, 1.2]) == pytest.approx(1 / 4)
    assert p_valor(0.9, [1.0, 1.1, 1.2]) == pytest.approx(1.0)


# ------------------------------------------------------------- 3) bootstrap por bloques vs iid
def test_bootstrap_bloques_vs_iid_independientes():
    rng = np.random.default_rng(5)
    r = rng.normal(0.02, 1, 1500)
    a, b = bootstrap_iid(r, n=1500), bootstrap_bloques(r, n=1500, bloque=20)
    assert abs(a["pf_lo"] - b["pf_lo"]) < 0.06


def test_bootstrap_bloques_mas_ancho_con_dependencia():
    """Rachas largas de signo constante: el bootstrap iid subestima la incertidumbre."""
    rng = np.random.default_rng(9)
    bloques = rng.choice([-0.4, 0.5], size=60)
    r = np.repeat(bloques, 20) + rng.normal(0, 0.2, 1200)
    a, b = bootstrap_iid(r, n=1500), bootstrap_bloques(r, n=1500, bloque=20)
    assert (b["pf_hi"] - b["pf_lo"]) > 1.5 * (a["pf_hi"] - a["pf_lo"])


def test_bootstrap_por_dia():
    rng = np.random.default_rng(2)
    dias = np.repeat(np.arange(300), 3)
    r = rng.normal(0.0, 1, 900)
    b = bootstrap_bloques(r, grupos=dias, n=800)
    assert b["pf_lo"] < 1.0 < b["pf_hi"]


# ------------------------------------------------------------- costos
def test_cost_model_legado_lsr_reproduce_valores_historicos():
    def f(i, a):
        return costo_pts(i, a, tabla=TABLA_LSR_V1)
    assert f("NQ", 2018) == pytest.approx(1.225) and f("NQ", 2020) == pytest.approx(1.475)
    assert f("NQ", 2024) == pytest.approx(1.10)
    assert f("ES", 2018) == pytest.approx(0.84) and f("ES", 2020) == pytest.approx(0.965)
    assert f("ES", 2024) == pytest.approx(0.84)


@pytest.mark.parametrize("anio", [2018, 2024, 2026])
def test_costo_trade_nq_ibkr(anio):
    """NQ redondo: comision $4.30 + slippage ($5 x 2) + spread (0.25 pts = $5 x 2) = $24.30 = 1.215 pts."""
    c = costo_trade("NQ", anio)
    assert c["slippage_usd"] == pytest.approx(10.00) and c["total_pts"] >= 1.10
    if anio >= 2024:
        assert c["comision_usd"] == pytest.approx(4.30) and c["spread_usd"] == pytest.approx(10.00)
        assert c["total_usd"] == pytest.approx(24.30, abs=0.01)
        assert c["total_pts"] == pytest.approx(24.30 / 20.0)


@pytest.mark.parametrize("anio", [2018, 2024, 2026])
def test_costo_trade_es_ibkr(anio):
    """ES redondo 2024+: comision $4.30 + slippage ($12.50 x 2) + spread (0.25 pts = $12.50 x 2) = $54.30 = 1.086 pts."""
    c = costo_trade("ES", anio)
    assert c["slippage_usd"] == pytest.approx(25.00) and c["spread_usd"] == pytest.approx(25.00)
    if anio >= 2024:
        assert c["comision_usd"] == pytest.approx(4.30)
        assert c["total_usd"] == pytest.approx(54.30, abs=0.01)
        assert c["total_pts"] == pytest.approx(54.30 / 50.0)
    else:                                               # anios previos: comision = max(4.30, 4.50 de LSR v1)
        assert c["total_usd"] == pytest.approx(54.50, abs=0.01)


@pytest.mark.xfail(strict=True, reason="Con los valores dictados (1 tick de slippage + 1 tick de spread por lado) el ES "
                   "redondo cuesta 1.086 pts, no >= 1.10. LSR v1 en ES costaba 0.84-0.965 pts (el 1.10 era de NQ).")
@pytest.mark.parametrize("anio", [2024, 2025, 2026])
def test_costo_es_ge_1_10_pts_solicitado(anio):
    assert costo_trade("ES", anio)["total_pts"] >= 1.10


@pytest.mark.parametrize("inst", ["NQ", "ES"])
@pytest.mark.parametrize("anio", list(range(2016, 2027)))
def test_costo_nuevo_no_es_menor_que_lsr_v1(inst, anio):
    """Los costos nuevos (con spread) no pueden ser MENORES que los de LSR v1 en ningun anio: sesgaria a favor."""
    assert costo_pts(inst, anio) >= costo_pts(inst, anio, tabla=TABLA_LSR_V1) - 1e-9


def test_costo_trade_contratos_y_marcas_de_verificacion():
    from validacion.cost_model import NOTA_PREVIO, costo_anio
    assert costo_trade("NQ", 2025, n_contratos=3)["total_usd"] == pytest.approx(3 * 24.30)
    est = estado_verificacion()
    assert est["verificados"] == 0 and len(est["sin_verificar"]) == 5 * 11   # 5 instrumentos x 2016-2026
    assert "VERIFICAR CON IBKR" in costo_trade("ES", 2024)["estado"]
    assert costo_anio("NQ", 2020).nota.startswith(NOTA_PREVIO) and "dictados" in costo_anio("NQ", 2025).nota


def test_spread_nunca_cero_en_instrumentos_usables():
    from validacion.cost_model import CONTRATOS, TABLA_IBKR
    assert all(c.spread_usd_lado > 0 for c in TABLA_IBKR.values())
    assert costo_trade("GC", 2025)["total_usd"] == pytest.approx(4.30 + 20.0 + 20.0)


def test_btc_mbt_bloqueados_hasta_verificar():
    with pytest.raises(ValueError, match="NO USAR"):
        costo_trade("BTC", 2025)
    with pytest.raises(ValueError, match="NO USAR"):
        costo_trade("MBT", 2025)
    assert "NO USAR HASTA VERIFICAR" in costo_trade("BTC", 2025, permitir_no_verificado=True)["estado"]

if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-q"]))
