"""Modo CFD de cost_model: tablas separadas, brokers, valores dictados, sin invenciones."""
import pytest

from validacion import (TABLA_CFD, comparar_brokers_cfd, costo_cfd_usd, costo_nq_futuro_usd,
                        costo_pts, costo_trade, costo_trade_cfd, estado_verificacion_cfd)
from validacion.cost_model import CONTRATOS_CFD, COSTO_BACKTEST_US100_PTS, TABLA_IBKR, costo_backtest_us100


def test_tablas_separadas_futuros_y_cfd():
    assert not set(TABLA_CFD) & set(TABLA_IBKR)
    assert costo_trade("NQ", 2025)["total_usd"] == pytest.approx(24.30)           # modo por defecto = futuros, intacto
    assert costo_trade("NQ", 2025, modo="futuros")["total_usd"] == pytest.approx(24.30)


def test_us100_valor_punto_lote_es_100():
    """1 lote US100 = $100/punto (IC Markets estandar). Verificar que el modelo usa el valor correcto."""
    assert CONTRATOS_CFD["US100"].valor_punto_lote == pytest.approx(100.0)


def test_us100_ic_markets_spread_dictado():
    c = costo_trade("US100", 2025, modo="cfd")
    # max spread por defecto = 1.5 pts; 1 lote x $100/pt = $150 total_usd
    assert c["total_pts"] == pytest.approx(1.5)
    assert c["total_usd"] == pytest.approx(1.5 * 100.0)
    assert costo_trade_cfd("US100", usar_spread="min")["total_pts"] == pytest.approx(1.0)
    assert costo_pts("US100", 2025, modo="cfd", usar_spread="medio") == pytest.approx(1.25)
    assert "VERIFICAR CON IC MARKETS" in c["estado"] and c["comision_usd"] == 0.0 and c["slippage_modelado"] is False


def test_lotes_pequenos():
    c = costo_trade("US100", 2025, n_contratos=0.05, modo="cfd")
    # 1.5 pts max spread x $100/pt/lote x 0.05 lotes = $7.50
    assert c["total_usd"] == pytest.approx(1.5 * 100.0 * 0.05)


def test_xauusd_y_btcusd_ic_markets():
    assert costo_trade_cfd("XAUUSD", usar_spread="max")["total_pts"] == pytest.approx(0.30)
    assert costo_trade_cfd("XAUUSD", usar_spread="min")["total_pts"] == pytest.approx(0.15)
    assert costo_trade_cfd("BTCUSD", usar_spread="min")["total_pts"] == pytest.approx(10.0)
    assert costo_trade_cfd("BTCUSD")["total_pts"] == pytest.approx(50.0)


def test_slippage_se_suma_si_se_modela():
    c = costo_trade_cfd("US100", slippage_pts_lado=0.5)
    assert c["total_pts"] == pytest.approx(1.5 + 1.0) and c["slippage_modelado"] is True


def test_sin_dato_no_se_inventa():
    with pytest.raises(ValueError, match="sin spread"):
        costo_trade_cfd("US100", broker="Pepperstone")
    with pytest.raises(ValueError, match="sin spread"):
        costo_trade_cfd("XAUUSD", broker="XM")
    assert costo_trade_cfd("US100", broker="Pepperstone", spread_pts=1.2)["total_pts"] == pytest.approx(1.2)
    with pytest.raises(ValueError, match="swap sin dato"):
        costo_trade_cfd("US100", noches=1)
    assert costo_trade_cfd("US100", noches=2, swap_pts_noche=0.3)["swap_pts"] == pytest.approx(0.6)


def test_comparacion_brokers_y_columna_broker():
    cmp = comparar_brokers_cfd("US100")
    # 1 lote x $100/pt x 1.5 pts = $150 IC Markets; XM spread max 2.5 pts x $100 = $250
    assert cmp["IC Markets"] == pytest.approx(1.5 * 100.0)
    assert cmp["XM"] == pytest.approx(2.5 * 100.0)
    assert cmp["Pepperstone"] is None
    assert {b for _, b in TABLA_CFD} == {"IC Markets", "Pepperstone", "XM"}
    assert all(c.broker == b for (_, b), c in TABLA_CFD.items())


def test_ninguna_fila_cfd_esta_verificada_y_modo_invalido():
    est = estado_verificacion_cfd()
    assert est["verificados"] == 0 and len(est["sin_verificar"]) == 9
    assert "Pepperstone" in " ".join(est["sin_spread"])
    with pytest.raises(ValueError, match="modo"):
        costo_trade("NQ", 2025, modo="otro")
    with pytest.raises(KeyError):
        costo_trade_cfd("EURUSD")


# ---------------------------------------------------------------- tests de utilidades simples (operativa real)

def test_costo_cfd_usd_lotes_tipicos():
    """Verifica los costos reales de US100 CFD por lote (spread 1.5 pts + slippage 0.5 pts RT = 2.0 pts x $100/pt)."""
    assert costo_cfd_usd(0.01, 1.5, 0.5) == pytest.approx(2.00)
    assert costo_cfd_usd(0.05, 1.5, 0.5) == pytest.approx(10.00)
    assert costo_cfd_usd(0.10, 1.5, 0.5) == pytest.approx(20.00)
    assert costo_cfd_usd(1.00, 1.5, 0.5) == pytest.approx(200.00)


def test_costo_cfd_usd_con_spread_min():
    """Con spread minimo 1.0 pts + slippage 0.5 pts RT = 1.5 pts x $100/pt x lote."""
    assert costo_cfd_usd(0.01, 1.0, 0.5) == pytest.approx(1.50)
    assert costo_cfd_usd(0.10, 1.0, 0.5) == pytest.approx(15.00)


def test_costo_nq_futuro_usd_tipico():
    """Costo redondo NQ futuro: spread 0.25 pts + slippage 0.50 pts RT + comision $4.30 = 0.75 pts x $20 + $4.30."""
    assert costo_nq_futuro_usd(0.25, 0.50, 4.30) == pytest.approx(14.30)
    # Rango $14-15 documentado
    assert 14.0 <= costo_nq_futuro_usd(0.25, 0.50, 4.30) <= 15.0


def test_cfd_vs_futuro_modo_correcto():
    """CFD opera en modo cfd; NQ futuro en modo futuros. No se mezclan."""
    c_cfd = costo_trade("US100", 2025, n_contratos=0.01, modo="cfd", slippage_pts_lado=0.25)
    c_fut = costo_trade("NQ", 2025, modo="futuros")
    assert c_cfd["modo"] == "cfd"
    assert c_fut["total_usd"] == pytest.approx(24.30)  # tabla IBKR intacta para proxy


def test_costo_backtest_us100_modo_cfd():
    """Precios NQ, costos USTEC: spread 1.5 + slippage 0.5 RT = 2.0 pts por trade."""
    assert COSTO_BACKTEST_US100_PTS == pytest.approx(2.0)
    assert costo_backtest_us100(0.01)["total_pts"] == pytest.approx(2.0)
    assert costo_backtest_us100(0.01)["total_usd"] == pytest.approx(2.00)
    assert costo_backtest_us100(0.10)["total_usd"] == pytest.approx(20.00)
    assert costo_cfd_usd(0.01) == pytest.approx(2.00)
