"""Los config.yaml de las estrategias legado deben coincidir con las constantes de sus motores (anti-deriva)."""
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parents[1]))   # permite `python tests/<archivo>.py` desde cualquier carpeta
from pathlib import Path

import pytest

from scripts._comun.config import cargar_config
from scripts.us100_v1 import motor_us100 as u

RAIZ = Path(__file__).resolve().parents[1]


def test_config_us100_v1():
    c = cargar_config(RAIZ / "scripts" / "us100_v1")
    assert c["ventana"] == dict(n_rth=u.N_RTH, fin_ventana_idx=u.FIN_VENTANA, max_entrada_idx=u.MAX_ENTRADA, s_min_idx=u.S_MIN)
    assert c["datos"]["desde"] == u.DESDE and c["datos"]["offset_servidor_h"] == u.OFFSET_SERVIDOR_H
    assert c["perfil_bin_pts"] == u.BIN
    assert c["datos"]["archivo"].endswith(u.CSV.name)


def test_config_lsr():
    import sys
    sys.path.insert(0, str(RAIZ / "scripts" / "lsr"))
    import motor_lsr as m
    c = cargar_config(RAIZ / "scripts" / "lsr")
    assert c["tick"] == m.TICK and c["multiplicador"] == m.MULT and c["min_barras_rth"] == m.MIN_BARRAS_RTH
    assert tuple(c["rejilla"]["k_sl_atr"]) == m.KS and tuple(c["rejilla"]["m_tp_atr"]) == m.MS
    assert tuple(c["referencia_pf_costo"]) == m.REF


def test_config_g2():
    import sys
    sys.path.insert(0, str(RAIZ / "scripts" / "g2"))
    import motor_g2 as m
    c = cargar_config(RAIZ / "scripts" / "g2")
    assert (c["perfil"]["bin_pts"], c["perfil"]["area_valor_pct"]) == (m.BIN0, m.VA_PCT)
    s = c["senal"]
    assert (s["barrido_pts"], s["retest_pts"], s["reclaim_barras"], s["retest_fill_1m"], s["hora_max_min"]) == \
        (m.SWEEP0, m.RETEST0, m.RECLAIM_BARS, m.RETEST_FILL_1M, m.HORA_MAX)
    assert (c["salida"]["sl_pts"], c["salida"]["tp_pts"]) == (m.SL0, m.TP0)
    assert (c["calibracion"]["precio"], c["calibracion"]["atr"]) == (m.P_CAL, m.ATR_CAL) and c["min_barras"] == m.MIN_BARRAS

if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-q"]))
