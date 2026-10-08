# NQ Trading Lab

Laboratorio de backtesting intradía para el Nasdaq-100 (NQ): estrategia **PDH/PDL** (máximo/mínimo del día
anterior), **ORB** (Opening Range Breakout) y **VWAP**, con filtros por indicadores (ATR, VWAP, RSI, Bollinger),
motor de simulación vela a vela y validación **walk-forward** (In-Sample / Out-of-Sample).

## Estructura

```
.
├── main.py                  # comparación de estrategias x filtros x parámetros
├── requirements.txt
├── config/
│   └── config.py            # ticker, intervalo, rutas, grids, API key (por entorno)
├── src/
│   ├── datos.py             # cargar_datos(): CSV local -> Tiingo -> yfinance
│   ├── indicadores.py       # ATR, VWAP, RSI, Bollinger, PDH/PDL
│   ├── motor/motor_estrategias.py   # puente estrategia -> motor del laboratorio
│   └── estrategias/
│       ├── base.py          # Senal + clase base Estrategia
│       ├── pdh_pdl.py  orb.py  vwap.py
│       └── filtros.py       # filtros ex-ante (atr, vwap, rsi, bollinger)
├── scripts/
│   ├── pdh_pdl_lab.py       # laboratorio original (grid, régimen, movimiento), sin cambios de lógica
│   ├── pdh_pdl_mt5_explorer.py
│   ├── analisis_movimiento.py   # punto de entrada del análisis de trayectoria
│   ├── descargar_tiingo.py  # descarga datos de Tiingo a data/raw/
│   └── archivo/estrategias_monolitico.py   # estrategias.py antiguo (ya dividido en src/estrategias/)
├── data/{raw,processed}/    # CSVs originales / con indicadores (ignorados por git)
├── resultados/{csv,png,reportes}/
├── tests/                   # pytest
└── notebooks/
```

## Instalación

```powershell
pip install -r requirements.txt
```

Ejecuta **todo desde la raíz del proyecto** (los módulos se importan como `config.config`, `src.*`, `scripts.*`).

## Uso

```powershell
python main.py                                  # config/config.py (INTERVALO=5m)
python main.py --intervalo 1h                   # usa data/raw/NQ_1h.csv (2 años)
python main.py --estrategia orb                 # pdh_pdl | orb | vwap | all
python main.py --config mi_config.py           # constantes alternativas (pisan las de config.py)
python main.py --ticker ES=F --intervalo 15m

python -m pytest tests                          # tests
python -m scripts.descargar_tiingo              # descarga QQQ 5m y 1h a data/raw/
python -m scripts.analisis_movimiento           # trayectoria post-toque PDH/PDL
python -m scripts.pdh_pdl_lab                   # laboratorio original (también: movimiento | regimen | filtros)
```

Fuentes de datos, en orden: CSV `data/raw/<CSV_PREFIJO>_<intervalo>.csv` → Tiingo (si hay API key) → yfinance
(solo 60 días en 5m/15m/30m, 730 en 1h). Salidas: `resultados/csv/comparacion_estrategias.csv` (y una copia por
intervalo) y `data/processed/<prefijo>_<intervalo>_indicadores.csv`.

## API key de Tiingo

1. Cuenta gratis en <https://www.tiingo.com/>.
2. Token en <https://www.tiingo.com/account/api/token>.
3. `$env:TIINGO_API_KEY = "tu_token"` (nunca en el código; `.env` está en `.gitignore`).
4. `python -m scripts.descargar_tiingo --ticker QQQ --intervalos 5m 1h --inicio 2020-01-01`

Limitaciones: Tiingo **no tiene futuros**; su feed intradía es de acciones/ETFs, así que se usa QQQ como proxy.
El script lo guarda como `QQQ_5m.csv` (no pisa tu `NQ_5m.csv`). Para usarlo en `main.py` pon en la config
`CSV_PREFIJO = "QQQ"` y `ESCALA_PUNTOS ≈ 0.03` (SL/TP/spread están en puntos NQ). Para NQ real con años de 5m, deja un
CSV exportado de tu bróker en `data/raw/NQ_5m.csv`. La ruta de Tiingo no se ha podido probar sin API key.

## Interpretar los resultados

`comparacion_estrategias.csv` tiene una fila por (estrategia, filtro, SL, TP, MaxTrades) con métricas `_IS` y `_OOS`
(Profit Factor, Win Rate, Max DD %, Sharpe, Sortino, Expectancy, Retorno %, trades) y un `Veredicto`:

| Veredicto | Significado |
|---|---|
| `ROBUSTO` | PF IS > 1, PF OOS ≥ 1 y ≥ 70 % del IS (`(n<30)` = pocos trades OOS) |
| `DEGRADA` | sigue ganando en OOS pero cae > 30 % |
| `OVERFITTING` | PF OOS < 1 |
| `SIN EDGE IS` / `SIN DATOS OOS` | PF IS ≤ 1 / menos de 8 trades OOS |

El ranking usa solo IS; el OOS es el examen. Con ~500 configuraciones, ~5 % saldrá "robusta" por azar:
exige consistencia entre temporalidades y n ≥ 30 OOS. El motor asume SL antes que TP si una vela toca ambos.

## Notas sobre el régimen de mercado cambiante

Un edge medido en un periodo puede desaparecer en otro: volatilidad y tendencia cambian (el NQ pasó de ~4.200 en 2015 a
~31.000 aquí). Por eso: (1) el walk-forward separa el pasado del futuro; (2) `python -m scripts.pdh_pdl_lab regimen`
desglosa el PF por año, semestre, volatilidad y tendencia; (3) los filtros ATR_ratio comparan la volatilidad con su
propia media reciente en vez de usar umbrales absolutos. 60 días de 5m son un solo régimen: no concluyas con ellos.

## Changelog

### 2026-10-08 — Reorganización del proyecto
**Antes:** todo en la raíz (`config.py`, `datos.py`, `indicadores.py`, `estrategias.py`, `motor_estrategias.py`,
`pdh_pdl_lab.py`, `pdh_pdl_mt5_explorer.py`) y CSV/PNG mezclados en `resultados/` y `data/`.

| Origen | Destino |
|---|---|
| `config.py` | `config/config.py` |
| `datos.py`, `indicadores.py` | `src/` |
| `motor_estrategias.py` | `src/motor/motor_estrategias.py` |
| `estrategias.py` | dividido en `src/estrategias/{base,pdh_pdl,orb,vwap,filtros}.py`; original en `scripts/archivo/` |
| `pdh_pdl_lab.py`, `pdh_pdl_mt5_explorer.py` | `scripts/` |
| `data/*.csv` | `data/raw/` |
| `resultados/*.csv`, `*.png` | `resultados/csv/`, `resultados/png/` |

**Imports:** `from config import X` → `from config.config import X` (o `from config import config`);
`from datos import Y` → `from src.datos import Y`; `import pdh_pdl_lab` → `from scripts import pdh_pdl_lab`;
estrategias → `from src.estrategias.pdh_pdl import EstrategiaPDH_PDL`, `...orb import EstrategiaORB`, `...vwap import EstrategiaVWAP`.
**Rutas:** `config.py` define `DIR_DATOS_RAW`, `DIR_RESULTADOS_CSV`, etc. con `pathlib`; el laboratorio escribe en
`resultados/csv|png` y cachea en `data/raw`. **Nuevo:** `--estrategia`, `--config`, `descargar_tiingo.py`, tests.
Lógica interna sin cambios (verificado: mismas métricas antes y después).
