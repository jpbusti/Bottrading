# Diagnóstico de capacidades — Proyecto Trading (NQ/ES)

Fecha: 2026-10-08. Todo lo marcado "verificado" se comprobó en tu PC (Python, git, archivos, variables de entorno por nombre). Lo marcado [NO VERIFICADO] no pude comprobarlo.

## Hechos verificados

- **Python 3.12.2** con: pandas 2.2.2, numpy 1.26.4, scipy 1.12.0, scikit-learn 1.4.1, matplotlib 3.8.4, databento 0.87.0, yfinance 1.7.0, duckdb 1.5.5, pyarrow 25, zstandard, ta 0.11.0, pytest 9.1.1, xgboost, metatrader5.
- **NO instalados**: statsmodels, arch, vectorbt, backtrader, quantstats, polars, numba.
- **Internet**: sí (pypi.org respondió 200). Se pueden instalar paquetes con pip.
- **Git**: git 2.56 instalado, remoto `origin = https://github.com/jpbusti/Bottrading.git`, rama `main`, usuario `jpbusti`, credential.helper `manager`. `git ls-remote` (lectura) funciona. `git push --dry-run` falló desde esta sesión con "could not read Username" porque no puedo abrir el login interactivo. Conclusión: **leer sí; push desde aquí no está verificado**. Funciona desde GitHub Desktop (ahí ya hiciste commits). `gh` (GitHub CLI) NO está instalado.
- **Claves de datos**: ninguna presente. Revisé variables de entorno (proceso, usuario, máquina) buscando DATABENTO, TIINGO, POLYGON, KEY, TOKEN: **DATABENTO_API_KEY no está definida**, TIINGO_API_KEY tampoco. No hay archivos `.env`. Los scripts de descarga la exigen por variable de entorno.
- **Carpeta del repo real**: `C:\Users\RYZEN\Desktop\MT\Bottrading\trade\`. La carpeta `claude/` con `PREREGISTRO_LSR_V1.md` y `RESULTADO_LSR_V1.md` **no existe ahora en el disco** (probablemente se borró en la limpieza del commit 8f55d12). Se puede recuperar con `git log`/`git show` si hace falta.

## Datos en `data/raw/`

| Archivo | Contenido (verificado) |
|---|---|
| `NQ_databento_1m_10y_RTH.csv.gz` | 981,600 velas 1 min, sesión regular, 2016-10-10 → 2026-10-06 |
| `ES_databento_1m_10y_RTH.csv.gz` | 989,804 velas, 2016-10-10 → 2026-10-07, 39 rolls, 2,577 sesiones |
| `NQ_databento_1m.csv` | 350,561 velas, 2025-10 → 2026-10, incluye sesión extendida (ETH) |
| `NQ_1d.csv`, `NQ_1h.csv` | diario/horario (origen Yahoo, para estudios viejos) |
| `databento_crudo/*.zst` | descargas originales comprimidas (ES 10 años; NQ 2016-2021) |
| `calidad/` | reporte de calidad (sin duplicados, 0 OHLC incoherentes, 4 huecos >5 min) y tablas de rolls |

Pendiente/cuestionable: el reporte de calidad solo describe NQ 2016-2021 y ES. NQ 2021-2026 RTH está en el .gz de 10 años pero no vi un reporte de calidad específico para ese tramo [VERIFICAR]. Saltos en rolls de +57 pts promedio en NQ (hasta +223) indican que la serie `c.0` **no está back-adjusted**; el proyecto resuelve esto extrayendo contratos individuales (`extraer_contratos*.py`).

## Qué cubre ya el código existente

| Elemento | Dónde | Estado |
|---|---|---|
| Costos por año | `scripts/lsr/motor_lsr.py:36` `costo_pts(inst, anio)` (slippage 0.5 + spread por año + comisión) | Existe, pero está marcado `[VERIFICAR]` en el propio código; solo spread varía por año (2016-19, 2020, 2021+), la comisión es fija |
| Walk-forward | `motor_lsr.py:300` `walk_forward` | Ventana expansiva, un fold por año desde 2019 (≈8 folds). Elige combo por mayor PF de entrenamiento. OK según metodología |
| Placebo | `run_lsr.py:88` (niveles de D-2) | **Solo placebo de nivel.** No hay placebo de timing aleatorio ni de dirección invertida |
| IC90 del PF | `motor_lsr.py:260` `boot_pf` (percentiles 5/50/95, 5000 remuestras) | Existe, pero es bootstrap **iid** (ignora autocorrelación/agrupación de trades por día) |
| Monte Carlo drawdown | `motor_lsr.py:290` `mc_dd` (iid) y `g2/motor_g2.py:292` `monte_carlo_dd` (bloques de 20) | Existe |
| Criterios de aprobación | `g2/run_validacion.py` (C1..C5: PF≥1.15, IC90 exp>0, IC90 PF>1, años PF>1 ≥60%, PF>placebo) | Existe para G2; no cubre rejilla k/m ni sensibilidad temporal |
| Normalización por ATR | `src/indicadores.py`, `motor_lsr.py` (SL/TP como múltiplo) | Existe; no revisé a fondo si cumple k∈[0.8,1,1.2], m∈[1.5,1.75,2] [VERIFICAR] |
| Rejilla de parámetros | `resultados/archivo/resultados_grid*.csv`, `walk_forward_*.csv` | Hay histórico, la rejilla de LSR está dentro de `motor_lsr.py` (combos) |
| Subperíodos / exclusión de año | `g2/motor_g2.py:282` `por_anio` | Parcial: PF por año sí; "excluir cada año" no vi implementado |
| Tests | `tests/` (indicadores, estrategias) | Cubren solo `src/`, no los motores de `scripts/` |

Hallazgos de calidad del código (sin juzgar resultados): el motor LSR y el G2 son scripts separados con funciones duplicadas (`pf`, `boot_pf`, `resumen`); no hay un módulo común de validación reutilizable. La selección del walk-forward por "mayor PF" favorece combos con pocos trades (mitigado por `min_tr=30`, pero la metodología pide 300+ en la evaluación final).

---

## PARTE 1 — Auto-diagnóstico (SÍ / NO / PARCIALMENTE)

1. **Leer/escribir archivos**: SÍ. Ya lo hice en `trade/` (verificado).
2. **Ejecutar Python**: PARCIALMENTE. Python 3.12 + pandas/numpy/scipy sí. statsmodels, arch, vectorbt, backtrader, quantstats NO instalados (instalables por pip; internet funciona).
3. **Descargar datos**: PARCIALMENTE. Yahoo (yfinance) instalado; Databento instalado pero **sin API key**; Polygon sin paquete ni key. CSV locales sí.
4. **Procesar OHLCV**: SÍ. Hay datos limpios, reporte de calidad y extracción por contrato para roll.
5. **Indicadores (ATR, VWAP, PDH/PDL, opening range)**: SÍ. `src/indicadores.py`, `src/estrategias/{vwap,orb,pdh_pdl}.py`, `motor_lsr.py`.
6. **Backtests con costos por año**: PARCIALMENTE. Existe `costo_pts`, pero con supuestos marcados [VERIFICAR] y comisión sin variar por año.
7. **Walk-forward multi-fold**: SÍ. Expansivo anual, ~8 folds (2019-2026).
8. **Placebo**: PARCIALMENTE. Solo nivel (D-2). Faltan timing aleatorio y dirección invertida.
9. **IC90 del PF y bootstrap/MC**: PARCIALMENTE. Existe, pero iid; para trades agrupados por día conviene bootstrap por bloques/por día.
10. **Detectar curve-fitting**: PARCIALMENTE. Hay walk-forward y criterios en G2, falta rejilla k/m automática y sensibilidad "excluir año".
11. **Conectar a GitHub**: PARCIALMENTE. Remoto configurado y lectura OK; escritura/push no verificada desde esta sesión (sin login interactivo, sin `gh`). GitHub Desktop sí funciona para ti.
12. **Memoria del proyecto y chats hijos**: SÍ para el proyecto (puedo leer el timeline y threads con las herramientas del proyecto). La memoria de archivos del proyecto: no vi archivos de memoria en `trade/` [VERIFICAR].
13. **Buscar en internet**: SÍ en mi entorno (WebFetch/WebSearch disponibles como herramientas diferidas, y la red responde).
14. **APIs en tiempo real**: NO. No hay claves, ni broker conectado; además la tarea actual es backtesting, no ejecución.

---

## PARTE 2 — Qué necesito conectar

Catálogo: busqué en el registro de conectores de Claude con las palabras databento, polygon, market data, futures, github, jupyter. **No aparece Databento ni Polygon ni un conector de GitHub/Jupyter** entre los resultados. Aparecen otros de datos (FMP, Financial Datasets, LSEG, Webull, CoinDesk, alphaXiv) que no sirven para futuros NQ/ES intradía. No puedo afirmar que no exista en otro lado: [NO VERIFICADO fuera del registro].

| # | Nombre exacto | Para qué | Imprescindible | ¿Catálogo Anthropic? | Cómo configurarlo |
|---|---|---|---|---|---|
| 1 | **Databento API key** (variable `DATABENTO_API_KEY`), paquete `databento` ya instalado | Re-descargar/ampliar NQ y ES 1 min, y si hace falta tick/ETH para estudio de eventos | Solo si hay que bajar datos nuevos. **Hoy los datos 10 años ya están en disco**, así que no es urgente | No hay conector; se usa la librería Python (instalada) | PowerShell: `setx DATABENTO_API_KEY "db-..."` y reabrir la terminal. Clave en https://databento.com/portal → API Keys |
| 2 | **GitHub vía Git Credential Manager / GitHub Desktop** (ya tienes `credential.helper=manager`) | Versionar scripts y resultados | Imprescindible (versionado) | No hay conector GitHub propio de Claude en el catálogo que vi | Iniciar sesión una vez en GitHub Desktop (File → Options → Accounts). Para que yo pueda hacer push: hacer un `git push` desde tu terminal una vez para guardar la credencial |
| 3 | **Entorno Python local** (ya existe) | Ejecutar backtests | Imprescindible, ya cubierto | n/a | `pip install statsmodels arch quantstats` (ver Paso 1) |
| 4 | **Almacenamiento de resultados**: carpeta `resultados/` + commit a GitHub | Guardar trades CSV, logs | Imprescindible, ya existe | n/a | Sin conector; usar `resultados/<estudio>/` versionado. Archivos grandes (>50 MB) no al repo |
| 5 | Polygon, Yahoo, Tiingo | Fuentes alternativas | **No necesarios**: Databento ya cubre CME. Yahoo (NQ=F) tiene datos sucios para futuros | — | — |

---

## PARTE 3 — Skills que necesito

Existe y ya la puedo usar: `anthropic-skills:trading-methodology` (criterios de aprobación, placebos, costos, walk-forward). La leí completa.

| # | Nombre propuesto | Qué hace | Por qué | Imprescindible | ¿Existe? |
|---|---|---|---|---|---|
| 1 | `trading-methodology` | Protocolo de validación | Es la regla del proyecto | Sí | **Ya existe** |
| 2 | `walkforward-runner` (módulo Python, no skill) | `validacion/walkforward.py`: folds expansivos, PF por fold, fragilidad | Hoy está duplicado en `motor_lsr.py` | Sí | Hay que extraer del código existente |
| 3 | `placebo-suite` (módulo) | 3 placebos: nivel D-N, timing aleatorio, dirección invertida, con N sorteos y p-valor | Hoy solo hay el de nivel; el hallazgo clave del proyecto vino del placebo | Sí | Hay que crearlo |
| 4 | `pf-inference` (módulo) | IC90 del PF con bootstrap por día/bloques, percentil 5 | El actual es iid | Sí | Hay que crearlo (parte existe en `boot_pf`) |
| 5 | `cost-model` (módulo) | Tabla comisión+spread+slippage por año e instrumento, versionada y citada | Hoy es un `[VERIFICAR]` hardcodeado | Sí | Hay que crearlo y verificar con tu broker |
| 6 | `atr-grid-robustness` (módulo) | Rejilla k×m (9 puntos) y "excluir cada año" | Falta en el código | Sí | Hay que crearlo |
| 7 | `event-study` (módulo) | Retornos forward 30m/1h/2h/cierre vs baseline | Fase 0 de la metodología, el siguiente paso del proyecto | Sí | Hay que crearlo |
| 8 | Detección de régimen | Clasificar volatilidad/tendencia | Solo después de que una hipótesis pase el estudio de eventos | Útil, no ahora | No |
| 9 | Position sizing | Riesgo por trade | Sin edge validado no tiene sentido | Útil, no ahora | No |
| 10 | Análisis de resultados (Sharpe, DD) | quantstats o funciones propias | `maxdd`/`resumen` ya existen; quantstats es opcional | Útil | Parcial |

Nota: los puntos 2-7 son **código reutilizable en el repo** (`trade/validacion/`) más que skills de Claude. Tiene más sentido que vivan en el repo, con tests, y que la skill `trading-methodology` solo los invoque.

---

## PARTE 4 — Qué sobra

Lo que veo y no aporta a backtesting cuantitativo de NQ/ES:

- **Skills genéricas de documentos/oficina**: docx, pptx, pdf, xlsx, google-workspace, morning, schedule, setup-claude, import-memory, consolidate-memory, skill-creator, update-config, keybindings-help. No las necesito para este proyecto.
- **Navegador/escritorio** (built-in-browser, chrome-browser, computer-use) y servidores MCP asociados: ya tengo Python y archivos; navegador solo si hay que leer documentación puntual.
- **MCP de Shopify** (mock shop, productos, órdenes): irrelevante para trading. Candidato claro a desactivar.
- **Docs, Artifact, claude-api, plugin-authoring**: no aplican.
- **En el repo**: `scripts/pdh_pdl_lab.py` (74 KB) y `pdh_pdl_mt5_explorer.py` son estudios PDH/PDL anteriores; los resultados ya están archivados. `data/raw/NQ_1d.csv`, `NQ_1h.csv` (Yahoo) y `resultados/archivo/` solo tienen valor histórico. No los borré; la decisión de qué eliminar te toca a ti (el commit previo `b76d307` es tu respaldo).
- **MetaTrader5 / PyQt6 / PySide6 / transformers / torch**: instalados en el Python global, no los usa este proyecto (el `requirements.txt` solo lista 9 paquetes). Ruido, pero no estorban.

Mal configurado:
- `requirements.txt` no lista scipy ni scikit-learn aunque el código puede depender de ellos [VERIFICAR con un entorno limpio].
- `costo_pts` está marcado `[VERIFICAR]` y la comisión no varía por año.
- La carpeta `claude/` con pre-registro y resultado LSR v1 ya no está en disco.

---

## PARTE 5 — Plan de configuración

**Paso 1 — Instalar lo que falta (5 minutos)**
`pip install statsmodels quantstats` (arch solo si vamos a modelar volatilidad; vectorbt/backtrader NO hacen falta: el motor propio es más transparente y auditable). Congelar versiones: `pip freeze > requirements.lock.txt` solo de los paquetes del proyecto.

**Paso 2 — Dejar el push funcionando**
Abre una terminal en `trade/` y ejecuta un `git push` simple. Si pide login, inícialo ahí una vez; el Credential Manager lo recuerda y yo podré hacer push después. No hace falta tocar nada más.

**Paso 3 — Antes del próximo backtest, verifica**
1. Recupera `PREREGISTRO_LSR_V1.md` y `RESULTADO_LSR_V1.md` desde git (`git log --all -- claude/`) y vuelve a ponerlos en el repo.
2. Confirma costos reales con tu broker (comisión por lado, spread típico por año) y reemplaza el `[VERIFICAR]`.
3. Confirma que NQ 2021-2026 tiene reporte de calidad (hoy solo hay NQ 2016-2021 y ES).
4. Escribe el pre-registro de la nueva hipótesis **antes** de abrir datos.
5. `DATABENTO_API_KEY` solo si realmente necesitas datos nuevos (ETH/tick).

**Paso 4 — Prueba pequeña para validar todo el pipeline**
Usar LSR v1 (ya rechazada) como "control negativo": correr el nuevo módulo de validación sobre `trades_NQ_A.csv` y comprobar que reproduce PF 1.06 / IC90 inferior 0.84 / placebo ≥ real. Si el pipeline nuevo vuelve a rechazar LSR con los mismos números, confías en él. Después, correr un placebo trivial (señal aleatoria) y confirmar que da PF≈1 neto de costos.

---

## Resumen ejecutivo (10 líneas)

1. Tienes Python 3.12 con pandas/numpy/scipy y Databento; faltan statsmodels, quantstats y compañía (instalables).
2. Tienes 10 años de NQ y ES a 1 minuto (RTH) en disco, con reporte de calidad; no necesitas comprar ni descargar más datos para el próximo estudio.
3. No hay ninguna API key configurada (Databento/Tiingo); solo hace falta si descargas datos nuevos.
4. El código ya tiene walk-forward anual, costos por año, bootstrap de PF y MC de drawdown.
5. Lo que falta: placebos de timing y dirección, bootstrap por bloques, rejilla k/m y exclusión de año.
6. Los costos están marcados `[VERIFICAR]`; hay que fijarlos con tu broker.
7. Git lee bien; el push desde aquí no lo pude verificar (necesita un login previo en tu terminal).
8. No encontré conectores de Databento, Polygon ni GitHub en el catálogo; sobran Shopify, documentos y navegador.
9. Los pre-registros de LSR ya no están en el disco; recupéralos desde git.
10. Primero: instalar paquetes y dejar el push funcionando; después, extraer la validación a un módulo común y probarla con LSR v1 como control negativo.
