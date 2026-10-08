"""
PUENTE entre las estrategias/filtros y el motor del laboratorio (pdh_pdl_lab.py).

No se reescribe la simulación: se reutilizan lab.preparar_dias, lab.simular_trade (vía
backtest_completo) y lab.calcular_metricas. Lo único nuevo es sustituir en cada día la lista
de velas-señal (sig_idx / sig_dir) por las que genera la estrategia elegida.
"""
import numpy as np

from scripts import pdh_pdl_lab as lab
from src.estrategias.filtros import aplicar_filtro


class DatosPreparados:
    """DataFrame con indicadores + días del laboratorio (se construye UNA vez)."""
    def __init__(self, df, intervalo):
        self.df = df
        # igual que el laboratorio: con velas de 1h una sesión tiene ~7 velas
        self.dias = lab.preparar_dias(df, min_velas=5 if intervalo == "1h" else 10)
        self.k_dia = {d["fecha"]: k for k, d in enumerate(self.dias)}
        grupos = df.groupby("Date").indices          # fecha -> posiciones de fila
        self.ts_a_i = []                              # por día: {timestamp: índice de vela en el día}
        for d in self.dias:
            ts = df.index[grupos[d["fecha"]]]
            self.ts_a_i.append({t: i for i, t in enumerate(ts)})


def dias_con_senales(prep, senales):
    """Copia de los días con sig_idx/sig_dir sustituidos por las señales dadas."""
    por_dia = {}
    for s in senales:
        k = prep.k_dia.get(s.ts.date())
        if k is None:   # día no simulable (primer día o con pocas velas)
            continue
        por_dia.setdefault(k, {})[prep.ts_a_i[k][s.ts]] = s.direccion
    resultado = []
    for k, d in enumerate(prep.dias):
        sig = sorted(por_dia.get(k, {}).items())
        nuevo = dict(d)
        nuevo["sig_idx"] = np.array([i for i, _ in sig], dtype=int)
        nuevo["sig_dir"] = np.array([x for _, x in sig], dtype=int)
        resultado.append(nuevo)
    return resultado


def preparar_senales(prep, estrategia, filtro=None):
    """estrategia (+ filtro opcional) -> días listos para backtest_completo."""
    senales = aplicar_filtro(prep.df, estrategia.generar_senales(prep.df), filtro)
    return dias_con_senales(prep, senales)


def backtest_estrategia(prep, estrategia, params, filtro=None, dias=None):
    """
    Backtest de UNA estrategia con `params` (sl_puntos, tp_puntos, max_trades_dia, modo_salida,
    trailing_puntos, hora_ultima_entrada). `filtro` es opcional. `dias` permite pasar días ya
    preparados/recortados (IS/OOS) para no regenerar señales.
    Devuelve (DataFrame de trades, dict de métricas o None).
    """
    if dias is None:
        dias = preparar_senales(prep, estrategia, filtro)
    return lab.backtest_completo(dias, params)


def params_tp_fijo(sl, tp, max_trades, hora):
    return {"sl_puntos": sl, "tp_puntos": tp, "max_trades_dia": max_trades,
            "modo_salida": "TP_FIJO", "trailing_puntos": 0, "hora_ultima_entrada": hora}
