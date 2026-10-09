"""Modo CFD de cost_model: tablas separadas, brokers, valores dictados, sin invenciones."""
import pytest

from validacion import TABLA_CFD, comparar_brokers_cfd, costo_pts, costo_trade, costo_trade_cfd, estado_verificacion_cfd
from validacion.cost_model import TABLA_IBKR


def test_tablas_separadas_futuros_y_cfd():
    assert not set(TABLA_CFD) & set(TABLA_IBKR)
    assert costo_trade("NQ", 2025)["total_usd"] == pytest.approx(24.30)           # modo por defecto = futuros, intacto
    assert costo_trade("NQ", 2025, modo="futuros")["total_usd"] == pytest.approx(24.30)


def test_us100_ic_markets_spread_dictado():
    c = costo_trade("US100", 2025, modo="cfd")
    assert c["total_pts"] == pytest.approx(1.5) and c["total_usd"] == pytest.approx(1.5)   # max por defecto, 1 lote $1/pt
    assert costo_trade_cfd("US100", usar_spread="min")["total_pts"] == pytest.approx(1.0)
    assert costo_pts("US100", 2025, modo="cfd", usar_spread="medio") == pytest.approx(1.25)
    assert "VERIFICAR CON IC MARKETS" in c["estado"] and c["comision_usd"] == 0.0 and c["slippage_modelado"] is False


def test_lotes_pequenos():
    c = costo_trade("US100", 2025, n_contratos=0.05, modo="cfd")
    assert c["total_usd"] == pytest.approx(1.5 * 0.05)


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
    assert cmp["IC Markets"] == pytest.approx(1.5) and cmp["XM"] == pytest.approx(2.5) and cmp["Pepperstone"] is None
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
