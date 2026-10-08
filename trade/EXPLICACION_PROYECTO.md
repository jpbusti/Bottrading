# Tu proyecto de trading explicado desde cero

Fecha de la revisión: 2026-10-08. Carpeta revisada: `C:\Users\RYZEN\Desktop\MT\Bottrading\trade` (repositorio git en `Bottrading/`).

**Cómo está hecho este documento.** Recorrí el README, los scripts (cabeceras y lógica), los logs de resultados (`resultados/g2/` y `resultados/lsr/`), los CSV de `resultados/csv/` y `resultados/archivo/`, el reporte de calidad de datos, la configuración, los tests y el historial de git. Todo lo que cuento viene de ahí. Donde algo no existe o no pude confirmarlo, lo marco con **[NO ENCONTRADO]** o **[INFERIDO]**. No te doy recomendaciones, solo explico.

**Aviso importante sobre lo que pediste y no existe en la carpeta:**
- `claude/PREREGISTRO_LSR_V1.md` y `claude/RESULTADO_LSR_V1.md` **no están** en la carpeta. No existe ninguna carpeta `claude/`. El único rastro es el docstring de `scripts/lsr/motor_lsr.py`, que dice "reglas en claude/PREREGISTRO_LSR_V1.md". Por eso las reglas de LSR v1 las reconstruyo desde el código y desde el log de resultados, no desde el documento original.
- Lo mismo con G2: el README cita "los docs del Project (PREREGISTRO_G2_VALIDACION, RESULTADO_G2_VALIDACION)", pero esos archivos tampoco están en la carpeta.
- **Archivos de memoria del proyecto**: no hay ninguno dentro de la carpeta, y la carpeta de memoria de Claude para este proyecto está vacía. No puedo explicarte su contenido.
- **Chats hijos**: solo puedo ver los de esta sesión (ver Parte 2.8). Lo trabajado en chats anteriores solo lo conozco por lo que quedó escrito en el código, el README y los logs.

---

# PARTE 1: Qué es este proyecto

## 1.1 Qué intenta lograr
Es un laboratorio para responder una pregunta: **¿existe alguna regla mecánica y simple, sobre futuros del Nasdaq y del S&P 500, que gane dinero de forma consistente después de costos, o solo parece ganar por casualidad?**

Se han probado reglas basadas en niveles de precio del día anterior (máximo y mínimo de ayer), en el precio medio ponderado por volumen del día (VWAP) y en el rango de apertura. Cada regla se simula sobre datos históricos de minuto a minuto. La parte central del proyecto no es tanto "encontrar una estrategia" como **construir un proceso estricto para no engañarse**: reglas escritas antes de mirar los datos, costos incluidos, pruebas con otros años y otro instrumento, y un grupo de control (placebo).

Estado a hoy, según el README y los logs: **ninguna regla ha pasado la validación.** El gate (puerta de aprobación) llamado G2 dio "NO APROBADO" y la estrategia LSR v1 también fue rechazada.

## 1.2 Los instrumentos: NQ y ES
Son **futuros**: contratos estandarizados que cotizan en la bolsa CME y siguen un índice.
- **NQ** = E-mini Nasdaq-100. Sigue las 100 mayores empresas del Nasdaq (tecnología sobre todo). Cada punto del índice vale **20 USD** por contrato (en el código: `MULT = {"NQ": 20.0, "ES": 50.0}`).
- **ES** = E-mini S&P 500. Sigue las 500 mayores empresas de EE.UU. Cada punto vale **50 USD**.
- Un futuro tiene **vencimiento** (marzo, junio, septiembre, diciembre). Cada trimestre el mercado "salta" al contrato siguiente: eso se llama *rollover* y genera un salto de precio artificial entre contratos. Por eso el proyecto cuida tanto operar y calcular niveles con el mismo contrato (ver Glosario).
- Los datos son de **Databento**, velas de 1 minuto, solo en horario regular (09:30–16:00 hora de Nueva York) salvo un archivo con premercado.

## 1.3 Qué es "backtesting" y por qué importa
Backtesting es **simular una regla de trading sobre datos del pasado** como si la hubieras operado entonces, para ver cuánto habría ganado o perdido. Importa porque es la única forma barata de probar una idea sin arriesgar dinero. El problema es que es muy fácil hacerlo mal: si pruebas 600 combinaciones de parámetros y te quedas con la mejor, casi seguro encontraste suerte y no una ventaja real. Casi todo el proyecto es una defensa contra eso.

## 1.4 Qué es PF (Profit Factor) y por qué es la métrica central
**PF = ganancias totales brutas ÷ pérdidas totales brutas.**
- PF 1.15 significa: por cada dólar perdido, ganas 1.15. Neto, ganas 15 centavos por dólar arriesgado.
- PF 1.00 = no ganas ni pierdes. PF menor que 1 = pierdes dinero.
- PF 0.76 (el resultado de NQ en G2) = por cada dólar perdido, ganas 76 centavos; pierdes 24 centavos netos.

Es la métrica central porque resume en un solo número si el sistema gana o pierde, sin depender del tamaño de la cuenta. Ojo: un PF alto con pocos trades no significa nada (se puede deber a suerte), y por eso se calcula siempre con su intervalo de confianza.

## 1.5 Qué es IC90 y por qué el límite inferior debe superar 1.0
**IC90 = intervalo de confianza al 90 %.** Como tienes una muestra finita de trades, el PF que mediste es una estimación con incertidumbre. El proyecto la calcula con *bootstrap* (re-muestrear los trades miles de veces) y obtiene un rango, por ejemplo [0.67, 0.88]: "con 90 % de confianza, el PF verdadero está entre 0.67 y 0.88".

Se exige que **el límite inferior esté por encima de 1.0** porque eso significa que, incluso en el escenario pesimista razonable, la regla sigue ganando. Si el rango incluye el 1.0 (ejemplo: [0.87, 1.26]), no puedes distinguir la regla de una moneda al aire. Esa es la regla del proyecto: PF ≥ 1.15 **y** límite inferior del IC90 > 1.0.

---

# PARTE 2: Qué hay dentro del proyecto, archivo por archivo

Estructura real encontrada (todo bajo `Bottrading/trade/`):

```
.gitignore  README.md  requirements.txt  main.py  EXPLICACION_PROYECTO.md (este)
config/      src/      scripts/      tests/      data/      resultados/
```
Nota: el README menciona una carpeta `notebooks/` que **no existe**.

## 2.1 Raíz

| Archivo | Qué es | Para qué sirve | Estado |
|---|---|---|---|
| `README.md` | Guía del proyecto. | Describe las dos capas, la estructura, los datos, cómo ejecutar y las reglas. | Vigente; actualizado el 2026-10-08. |
| `main.py` | Motor original de comparación. | Prueba estrategias PDH/PDL, ORB y VWAP, combinadas con filtros y parámetros, con división en parte de entrenamiento (60 %) y examen (40 %). | Usado en la primera etapa. Funciona con `data/raw/NQ_1h.csv`. |
| `requirements.txt` | Lista de librerías. | pandas, numpy, yfinance, matplotlib, requests, tqdm, pytest, databento, zstandard. | Vigente. |
| `.gitignore` | Qué no sube a git. | Excluye caches, CSV/gz/zst de datos, `*.log`, `.env`, `_por_borrar/`. | Vigente. Ojo: por esto los datos y los logs **no están respaldados en GitHub**. |

## 2.2 `config/`
- `config.py`: configuración central del motor original (ticker NQ=F, intervalo, rutas, grids de stop-loss/take-profit, parámetros de ATR/RSI/Bollinger, umbrales de walk-forward). También tiene opciones de Tiingo (otra fuente de datos). **Vigente para `main.py`.**
- `__init__.py`: vacío, marca la carpeta como paquete.

## 2.3 `src/` (motor original reutilizable)
- `datos.py`: carga los datos (CSV local → Tiingo → yfinance) y los normaliza. Usado por `main.py`.
- `indicadores.py`: calcula ATR, RSI, VWAP, Bollinger y PDH/PDL del día anterior. Usado y probado por tests.
- `estrategias/base.py`: molde común de una estrategia (qué es una señal).
- `estrategias/pdh_pdl.py`: reversión al tocar el máximo/mínimo del día anterior (y una versión "sin gaps" que descarta días que abren lejos del rango).
- `estrategias/orb.py`: Opening Range Breakout (ruptura del rango de los primeros 30 minutos).
- `estrategias/vwap.py`: cruce del precio con el VWAP (seguimiento de tendencia o invertido).
- `estrategias/filtros.py`: filtros previos (ATR, VWAP, RSI, Bollinger) que permiten o bloquean una señal.
- `motor/motor_estrategias.py`: simula las operaciones vela a vela y calcula métricas.
- `__init__.py` (×3): vacíos.
Todo **ya usado** en la fase 1; ahora es la base "legada", todavía funcional.

## 2.4 `scripts/`

### 2.4.1 Laboratorio original
- `pdh_pdl_lab.py` (~1.480 líneas, el más grande): el laboratorio PDH/PDL original. Grid search (probar muchas combinaciones de stop y target), walk-forward, análisis de regímenes (tendencia/volatilidad), gráficos. `main.py` y `src/` lo importan, **por eso no se puede borrar**. Usado.
- `pdh_pdl_mt5_explorer.py`: la primera versión exploratoria PDH/PDL (descarga datos con yfinance, simula 20 días, calcula lotes). Origen de todo lo demás. Usado, hoy solo referencia.

### 2.4.2 `scripts/descarga/`
- `descargar_databento_5anios.py`: baja 5 años de NQ en 1m y guarda solo el horario regular. Usado (generó `NQ_databento_1m.csv` según el README: "último año con premercado").
- `descargar_validacion.py`: baja NQ 2016–2021 y ES 2016–hoy. Por tramos de 6 meses, con reintentos, **muestra el costo y pide escribir SI antes de gastar**. Usado (gracias a esto existen los `.zst` de datos pagados). La clave de Databento va en la variable de entorno `DATABENTO_API_KEY`, nunca en el código.

### 2.4.3 `scripts/marco_subastas/` (el "marco de subastas")
Tres variantes del mismo experimento en 1m sobre NQ (ver Parte 3):
- `marco_subastas.py`: versión base.
- `marco_subastas_stop_amplio.py`: misma lógica con stops más anchos.
- `marco_contexto_salidas.py`: añade contexto y tipos de salida.
Producen los CSV de `resultados/csv/marco_subastas_*`. **Ya usados.** El README dice que el marco "queda como herramienta visual hasta aprobar G2".

### 2.4.4 `scripts/g2/` (validación G2)
- `extraer_contratos.py`: lee los `.zst` crudos y saca las velas del horario regular de los 2 contratos más líquidos de cada día (sin pegar series). Genera `data/processed/{NQ,ES}_contratos_rth.pkl`. Usado.
- `motor_g2.py`: el motor de G2. Calcula niveles con **el mismo contrato que se opera**, escala los parámetros por ATR/porcentaje/fijo y calcula estadística (bootstrap, Monte Carlo). Usado.
- `control_test.py`: prueba de control: el motor nuevo debe **reproducir** n=172 trades y PF 1.629 del script original. Si no, el motor nuevo estaría mal. Usado.
- `run_validacion.py`: corre los 5 criterios del gate, sensibilidades y Monte Carlo, y escribe `resultados/g2/`. Usado; resultado: NO APROBADO.

### 2.4.5 `scripts/lsr/` (Liquidity Sweep Reversal v1)
- `extraer_contratos_ext.py`: igual que extraer pero incluyendo **premercado (04:00–16:00)**. Usado.
- `unir_nq.py`: une NQ por contrato (2016–2021) con el continuo c.0 (2021–2026), descartando días alrededor de cada roll. Usado.
- `motor_lsr.py`: el motor de LSR v1: contrato dominante, niveles PDH/PDL, velas de 5m, bloques A y B, stop y target por ATR o estructural, costos por año, FOMC/OPEX, bootstrap, Monte Carlo y walk-forward. Usado.
- `run_lsr.py`: corre el LSR pre-registrado completo y escribe `resultados/lsr/`. Usado; resultado: rechazada.

## 2.5 `tests/`
- `test_indicadores.py` y `test_estrategias.py`: pruebas automáticas (pytest) del motor original: que el ATR sea positivo, el RSI esté entre 0 y 100, el VWAP quede dentro del rango, que PDH/PDL sean del día anterior, que las señales tengan formato correcto.
- `conftest.py`: datos sintéticos de prueba. `__init__.py`: vacío.
**No hay tests para `scripts/g2` ni `scripts/lsr`** (el control de G2 hace de verificación, pero LSR no tiene equivalente que yo haya visto).

## 2.6 `data/`
- `raw/ES_databento_1m_10y_RTH.csv.gz` (11 MB): ES, 2016-10 → 2026-10, solo horario regular, **continuo sin ajustar**. Usado.
- `raw/NQ_databento_1m_10y_RTH.csv.gz` (12,7 MB): NQ, 2016-10 → 2026-10, mismo formato. Usado.
- `raw/NQ_databento_1m.csv` (22 MB): NQ último año **con premercado**; es el único con sesión Globex. Usado (control de G2 y marco de subastas).
- `raw/NQ_1d.csv`, `raw/NQ_1h.csv`: datos diarios y de 1h de yfinance, para `main.py`. Usados por el motor original.
- `raw/databento_crudo/*.zst` (76 MB ES + 34 MB NQ): **la fuente por contrato, pagada.** De aquí salen los demás archivos.
- `raw/calidad/ES_rolls.csv`, `NQ_rolls.csv`: fechas y saltos de cada rollover. `reporte_calidad_validacion.txt`: reporte de calidad.
- `processed/`: vacío (solo `.gitkeep`). Los `.pkl` se regeneran con `extraer_contratos.py`. Pendiente de generar si quieres re-correr.

**Calidad de datos (del reporte):** NQ 2016–2021: 495.425 velas, 1.289 sesiones, 19 rolls con salto medio de +57,9 puntos. ES: 989.804 velas, 2.577 sesiones, 39 rolls, salto medio +20 puntos. Sin duplicados ni velas incoherentes.

## 2.7 `resultados/`
- `g2/resultado_validacion.log` y `resumen_decision.csv`: veredicto G2 (NO APROBADO) con las 12 combinaciones (instrumento × método × criterios). Ver Parte 3.
- `lsr/resultado_lsr.log`: salida completa de LSR v1 (rejillas, walk-forward, sensibilidades, placebo). `trades_ES_A/B.csv`, `trades_NQ_A/B.csv`: cada operación simulada. `wf_oos_ES_A.csv`, `wf_oos_NQ_A.csv`: operaciones del walk-forward fuera de muestra. Usados.
- `csv/`: `marco_subastas_resultados.csv`, `marco_subastas_stop_amplio.csv`, `marco_subastas_mejor_variante_trades.csv`: resultados del marco de subastas.
- `png/`, `reportes/`: vacías.
- `archivo/` (copiado ahí en la limpieza de hoy y subido a git): **estudios PDH/PDL viejos**: grids de parámetros (`resultados_grid*.csv`, `top20_*.csv`), walk-forward (`walk_forward_*.csv`), regímenes (`resultados_regimen_*`, `pf_por_regimen_*.png`), ventanas rodantes, comparaciones por temporalidad (`comparacion_estrategias_*`), gaps (`pdh_pdl_gaps_*`), curvas de PF vs tiempo, equity, distribución del movimiento. **Ya usados**, solo para consulta.

## 2.8 Documentos de pre-registro, memoria y chats hijos
- `PREREGISTRO_LSR_V1.md`, `RESULTADO_LSR_V1.md`: **[NO ENCONTRADOS]** (ver aviso arriba). El docstring de `motor_lsr.py` resume las reglas del pre-registro (Parte 3.4).
- `PREREGISTRO_G2_VALIDACION` / `RESULTADO_G2_VALIDACION`: **[NO ENCONTRADOS]**; el README los menciona como "docs del Project".
- Memoria del proyecto: **[NO ENCONTRADA]** en la carpeta ni en la carpeta de memoria de Claude.
- Chats hijos que sí pude ver (en este proyecto de Claude):
  1. **"Organizar proyecto MT"** (hoy, 2026-10-08): se hizo un commit de respaldo, se archivaron los CSV/PNG de estudios viejos en `resultados/archivo/`, y se borraron `_por_borrar/` (~47 MB de velas regenerables) y `organizar_proyecto.py`. Quedó **1 commit local sin subir** (hay que dar "Push origin" en GitHub Desktop).
  2. **Este chat**: explicación del proyecto.
  Chats anteriores (los que hicieron G2, LSR, el marco): **[NO ACCESIBLES]**; no hay registro de ellos en lo que pude leer, salvo sus productos.

## 2.9 Historial de git (tres commits en total, todos del 2026-10-08)
`dbcefe3 "a"` (estructura inicial), `b76d307 "Respaldo..."`, `0384792 "Archivar resultados..."`, `8f55d12 "Limpieza..."`. El historial de git empieza hoy: no recoge la evolución anterior del proyecto.

---

# PARTE 3: Qué se ha hecho hasta ahora

## 3.1 Primera etapa: el laboratorio PDH/PDL con datos gratuitos
Empezó con la idea más simple: **si el precio toca el máximo (PDH) o mínimo (PDL) del día anterior, apuesta a que rebota.** Se descargaron datos de yfinance (limitados: 60 días en 5m, 730 en 1h) y se probó una rejilla enorme: stops de 10–50 puntos, targets de 0–100, 1–3 trades por día, trailing, horarios. Seguían los mismos patrones de la época de "grid search":
- Del `top20_configuraciones.csv`, la mejor del ranking tenía PF 1.34 con solo 46 trades.
- En `walk_forward_top10.csv`, la mejor configuración en entrenamiento (stop 25, target 100, 1 trade, 12:00) tenía **PF 2.19 en entrenamiento y 0.29 en examen.** Ejemplo de manual de *overfitting*.
- Las configuraciones "medianas" rondaban PF 1.03–1.12, con drawdowns de 18–42 %.
Lección: con muchos parámetros siempre aparece algo bonito en el pasado que se cae en el futuro.

## 3.2 Segunda etapa: datos reales de Databento y el último año
Con datos de calidad profesional (Databento, minuto a minuto, un año), la misma idea PDH/PDL dio **PF 0.84, -18,7 % de retorno y drawdown 30 %** en el año completo (`resultados_databento_validation.csv`, 236 trades). La referencia en yfinance parecía mejor (PF 1.47 y 1.19) pero era la muestra pequeña y gratuita: la diferencia sugiere que los resultados "buenos" venían de datos imprecisos o suerte. [INFERIDO: el README no lo explica].

## 3.3 El marco de subastas
**Qué es.** Una forma de leer el mercado inspirada en la teoría de subastas / perfil de volumen: el precio se mueve entre zonas de "valor justo". Se calcula con el volumen del día anterior:
- **POC**: el precio donde más volumen se negoció.
- **VAH / VAL**: techo y suelo del "área de valor" (donde ocurrió el 70 % del volumen).
- **PDH / PDL**: máximo y mínimo del día anterior.
- **VWAP/AVWAP** y **WOR** (rango del primer día de la semana) como filtros.
La idea de trading ("setup A"): el precio **barre** un nivel (lo supera un poco, atrapa operadores) y luego **vuelve** → entrada contraria. Se probaron variantes de entrada (al cierre o en el retest), filtro (ninguno, VWAP, VWAP+WOR) y salida (en el nivel o 1.5R).
**Resultados** (`marco_subastas_resultados.csv`, un año de NQ): PF 0.96 sin filtro, 1.08 con VWAP, 1.05 con VWAP+WOR, todos con IC que incluye negativos, y placebos de 0.63–0.98.
**Por qué solo queda como herramienta visual.** Porque ninguna variante superó los criterios; el README fija: "el marco PDH/PDL queda como herramienta visual hasta aprobar G2".

## 3.4 El PF 1.63 y por qué importa
Una regla del marco (**barrido + retest + filtro VWAP, stop 80 puntos, target 110 puntos**, costo 3 puntos) dio, en el último año de NQ, **n = 172 trades y PF 1.629** (`control_test.py` documenta "n=172, PF 1.629" como el valor que el motor nuevo debe reproducir; `top20_databento.csv` muestra otras configuraciones de ese año con PF 1.1–1.2 en todo el periodo y 1.6 en su mitad de examen, p. ej. SL 40/TP 110 sin filtro: PF 1.18 total, 1.63 en la segunda mitad). Era el **único PF positivo documentado**.

**Qué significa que sea "in-sample y no se replique".**
- *In-sample* (dentro de la muestra): los parámetros (SL 80, TP 110, el filtro VWAP) se eligieron *mirando ese mismo año*. Es como corregir un examen que ya viste: el 1.63 no prueba nada.
- *No se replica*: cuando la misma regla se probó en datos que nunca se usaron para elegirla (G2), dio PF 0.76–0.94 con costos. El 1.63 era suerte, o un efecto de ese año específico.

## 3.5 G2: la validación fuera de muestra
**Qué es G2.** Un "gate": una prueba pre-registrada con la regla **congelada** (barrido + retest + VWAP, SL 80/TP 110) sobre datos que no se usaron para diseñarla: **NQ 2016–2021** (5 años, otro periodo) y **ES 2016–2025** (otro instrumento, 10 años). Se probaron 3 formas de escalar la regla (ATR, porcentaje y puntos fijos) porque 80 puntos de NQ en 2017 no son lo mismo que en 2026.
**Los 5 criterios** (de `resumen_decision.csv`): C1 PF ≥ 1.15; C2 expectativa neta con IC90 > 0; C3 IC90 del PF > 1; C4 PF > 1 en ≥ 60 % de los años; C5 PF mayor que el placebo.
**Resultado: NO APROBADO.** Ninguna de las 4 combinaciones principales cumple todos los criterios:

| Prueba | Trades | PF | IC90 del PF | PF placebo |
|---|---|---|---|---|
| NQ 2016–21, escala ATR | 577 | 0.76 | [0.67, 0.88] | 0.68 |
| NQ 2016–21, escala % | 579 | 0.84 | [0.73, 0.97] | 0.88 |
| ES 2016–25, escala ATR | 926 | 0.79 | [0.70, 0.88] | 0.72 |
| ES 2016–25, escala % | 925 | 0.94 | [0.84, 1.06] | 0.86 |

Con costos al doble, el PF baja a ~0.54. Con costos a la mitad, sube a 0.90–0.95: **aun sin casi costos no llega a 1.15**. Por años, solo 2025 en ES (PF 1.22 con ATR) supera 1.0 entre 10 años.
Las filas con puntos fijos sin escalar (FIJO) dan PF ~1.01–1.05 pero sus IC cruzan el 1.0 y no pasan los demás criterios.

## 3.6 PDH/PDL: por qué importaba
Es la idea de partida y el nivel más usado en la comunidad de trading: el máximo/mínimo de ayer supuestamente es "memoria" del mercado donde compradores y vendedores reaccionan. Importaba como hipótesis madre. Resultado: por nivel en G2, PDH y PDL fueron los **peores** niveles (media de -0.30 R y -0.13 R en NQ ATR); VAH/VAL perdían menos. Es decir, tocar PDH/PDL no aportó ventaja medible.

## 3.7 LSR v1 (Liquidity Sweep Reversal): qué es y por qué fue rechazada
**Qué es.** "Reversión tras barrido de liquidez": el precio rompe el máximo o mínimo de ayer (barre las órdenes de stop de otros), pero no se sostiene, **vuelve a entrar al rango ("reclaim")** y se entra en contra de la ruptura. Reglas (del docstring de `motor_lsr.py`, que cita el pre-registro):
- Nivel: PDH/PDL del **contrato dominante del día anterior** (sin saltos de roll).
- **Bloque A**: barrido desde 09:30, entrada en 09:45–12:00 o 14:00–15:30, salida a las 15:59.
- **Bloque B**: barrido en premercado (04:00–09:30) con volumen > 1.5× el promedio, salida a las 09:29.
- Stop y target = k·ATR y m·ATR con k ∈ {0.8, 1.0, 1.2} y m ∈ {1.5, 1.75, 2.0}; también un caso "estructural".
- Costos modelados **por año**, filtros de calendario (FOMC, OPEX), un trade por día y bloque.
**Resultado en `resultado_lsr.log`:**

| | NQ Bloque A | ES Bloque A |
|---|---|---|
| Trades (WF fuera de muestra) | 901 | 909 |
| PF neto | 1.016 | 0.918 |
| IC90 inferior | 0.877 | 0.792 |
| Rejilla 9 combinaciones con PF ≥ 1.15 | 0/9 | 0/9 |
| Rejilla con límite inferior > 1.0 | 0/9 | 0/9 |

Todo el PF neto de la rejilla de NQ está entre 0.991 y 1.004: es decir, **el rango completo de parámetros está pegado a 1.0, que significa "no hay ventaja"**. Bloque B: NQ PF 1.165 con IC [0.73, 1.87] sobre 126 trades; ES PF 0.93 con 432 trades → "EXCLUIR". Veredicto del propio script: `{'NQ': False, 'ES': False}`.
Detalles del walk-forward NQ por año: 2019 0.94, 2020 1.23, 2021 1.11, 2022 0.90, 2023 1.16, 2024 0.87, 2025 1.25, 2026 0.75: bailan alrededor de 1 sin tendencia.

## 3.8 El test de placebo: el hallazgo más importante
**Qué es.** El placebo es el "grupo de control": se corre exactamente la misma regla, pero con **niveles falsos** (en LSR: los de D-2, el máximo/mínimo de *anteayer*, que no deberían tener significado especial hoy). Si la regla con los niveles reales rinde igual o peor que con niveles falsos, el nivel real no aporta nada: lo que se ve es ruido o el sesgo de la regla, no una propiedad de PDH/PDL.
**Qué encontró** (`resultado_lsr.log`, sensibilidades):
- NQ: PF neto con niveles reales **0.998**; con niveles falsos D-2 **1.085**. El placebo ganó.
- ES: reales **0.898**; placebo **0.980**. El placebo ganó.
- En G2: el PF real fue menor que el placebo en 4 de las 12 combinaciones medidas (C5 = False en NQ-PCT, NQ-FIJO, ES_último_año-PCT/FIJO) y en las otras apenas lo superó (0.76 vs 0.68).
**Por qué es el hallazgo más importante.** Porque la hipótesis de fondo del proyecto era "los niveles de ayer importan". Si los niveles falsos de anteayer rinden igual o mejor, **esa premisa no tiene respaldo en los datos**. Y no se arregla ajustando parámetros: afecta al fundamento. [Interpretación mía basada en los números; el RESULTADO_LSR_V1.md original no está en la carpeta.]

## 3.9 Errores cometidos y lo aprendido (documentados en el código/README)
1. **Overfitting con grid search** (3.1): elegir el mejor de cientos de combinaciones en los mismos datos. Se aprendió a exigir examen fuera de muestra y walk-forward.
2. **Datos gratuitos limitados** (yfinance 60 días): conclusiones con muestras mínimas (18–28 trades). Se pasó a Databento.
3. **Saltos de rollover**: unir contratos sin ajustar mete saltos artificiales (media +58 puntos en NQ) que pueden crear señales falsas. Se rehízo todo calculando niveles con el mismo contrato que se opera.
4. **Aprobar por el mejor año**: el 1.63 de un solo año. Por eso el README ahora dice: "Una regla no se aprueba por su mejor año".
5. **Costos**: sin costos o con costos subestimados todo se ve mejor. Ahora se incluyen y se prueba ×0.5 y ×2.
6. **Documentación dispersa**: los pre-registros y la memoria no están en la carpeta del proyecto (ver aviso inicial).

---

# PARTE 4: Qué se espera hacer ahora

Importante: **lo que sigue es lo que se desprende de la documentación y no una orden mía.** Del README y del código solo se confirma: "Nada de dinero real sin pasar los gates" y "el marco PDH/PDL queda como herramienta visual hasta aprobar G2". **No hay un documento de "próximos pasos" en la carpeta.** [El resto es la reconstrucción lógica a partir de lo aprendido, que es lo que pediste: marcado como INFERIDO.]

- **Siguiente paso lógico [INFERIDO]**: dejar de probar estrategias completas y hacer primero un **estudio de eventos**.
- **Estudio de eventos**: en vez de simular un trade con stop y target, se mide **qué hace el precio, en promedio, después de que ocurre un evento** (por ejemplo "después de tocar el VWAP", "después de romper el rango de apertura", "después de un pico de volumen"). Se mide a varios horizontes (5, 15, 30, 60 minutos) y se compara contra un grupo de control. Es el paso previo a diseñar una estrategia porque **responde "¿hay algo ahí?" antes de elegir stops y targets**, que son precisamente los parámetros con los que uno se engaña (overfitting).
- **Pre-registro**: escribir **antes de mirar los datos** la hipótesis, las reglas exactas, los parámetros, la muestra, las métricas y el criterio de aprobación/rechazo. Se hace antes para que no puedas (ni inconscientemente) ajustar la regla al resultado. LSR v1 y G2 tuvieron pre-registro (aunque los documentos no estén en la carpeta).
- **Familias de hipótesis que quedan por explorar** (las nombraste tú; en el código solo hay rastros): **VWAP** (ya existe `estrategias/vwap.py` y filtros), **opening range / ORB** (`estrategias/orb.py`), **volumen** (el perfil de volumen existe en el marco de subastas; picos de volumen se usan en el bloque B). Estructura tipo "mean reversion vs momentum", horarios y eventos macro (FOMC/CPI/NFP) aparecen como filtros de calendario en `motor_lsr.py` (FOMC y OPEX están implementados; CPI/NFP no los vi en el código).
- **Qué NO se debe hacer** (según lo que documentan el README y los logs, y lo que tú mencionaste):
  - **Re-optimizar LSR v1**: toda la rejilla está pegada a PF 1.0 y el placebo la supera; ajustar parámetros solo crearía una falsa ventaja (curve-fitting).
  - **Comprar más datos sin hipótesis**: ya hay 10 años de NQ y ES en 1m; el problema no es la cantidad de datos.
  - **Aprobar por el mejor año** o por un solo instrumento.
  - **Operar dinero real** antes de pasar los gates (regla explícita del README).
  - **Ignorar costos** (están en el centro del fracaso).

---

# PARTE 5: Glosario simple

- **PF (Profit Factor):** ganancias brutas ÷ pérdidas brutas. PF 1.15 = por cada dólar perdido, ganas 1.15.
- **IC90:** rango donde, con 90 % de confianza, está el valor verdadero; se usa para saber si el resultado es distinguible de la suerte.
- **Walk-forward:** probar la regla en una ventana de tiempo, elegir parámetros ahí, y evaluarla en el periodo siguiente; repetir avanzando. Imita lo que pasaría en la vida real.
- **In-sample:** los datos con los que se diseñó o eligió la regla; resultados ahí no prueban nada.
- **Out-of-sample:** datos que no se usaron para diseñar la regla; es el examen real.
- **Curve-fitting:** ajustar una regla hasta que encaje con el pasado, aunque no tenga ventaja real.
- **Overfitting:** versión técnica de curve-fitting; la regla "memoriza" el pasado y falla en el futuro.
- **Placebo:** control con niveles falsos o aleatorios; si la regla real no supera al placebo, no hay ventaja.
- **ATR:** Average True Range, el rango medio de movimiento diario (típicamente 14 días); mide cuánto se mueve el mercado.
- **VWAP:** precio promedio del día ponderado por volumen; referencia de "precio justo" intradía.
- **PDH / PDL:** Previous Day High / Low: máximo y mínimo del día anterior.
- **RTH:** Regular Trading Hours, 09:30–16:00 de Nueva York.
- **ETH:** Extended Trading Hours: fuera de RTH (premercado y nocturno); aquí solo se usó el premercado en LSR bloque B.
- **Rollover:** cambio de un contrato de futuros que vence al siguiente; genera un salto de precio artificial.
- **OPEX:** día de vencimiento de opciones (tercer viernes del mes); suele mover el volumen.
- **FOMC:** reunión de la Reserva Federal sobre tasas de interés; días de mucha volatilidad.
- **CPI:** Índice de Precios al Consumidor (inflación); dato macro que mueve el mercado.
- **NFP:** Non-Farm Payrolls, dato de empleo de EE.UU. (primer viernes del mes).
- **Drawdown:** caída desde el máximo de la cuenta hasta el siguiente mínimo; mide el peor momento.
- **Expectancy (expectativa):** ganancia promedio esperada por operación (en R o en dólares).
- **Sharpe:** retorno medio dividido por su variabilidad; mide rendimiento por unidad de riesgo.
- **Slippage:** diferencia entre el precio que querías y el que te dieron.
- **Spread:** diferencia entre el precio de compra y de venta; un costo implícito.
- **Back-adjusted:** serie de futuros donde los contratos antiguos se corrigen para eliminar los saltos de roll.
- **Panama (ajuste):** método de back-adjust que suma o resta la diferencia de cada roll a todo el historial anterior (conserva diferencias en puntos, distorsiona porcentajes). En este proyecto **no se usó**: se prefirió operar cada contrato por separado.
- **Bootstrap:** re-muestrear los trades al azar miles de veces para estimar un intervalo de confianza.
- **Monte Carlo:** simular miles de reordenamientos de los trades para ver el rango de drawdowns posibles.
- **Edge (ventaja):** ventaja estadística real y repetible de una estrategia.
- **Hipótesis:** afirmación concreta que se puede probar ("después de X, el precio hace Y").
- **Pre-registro:** escribir reglas y criterios de éxito antes de mirar los datos.
- **R:** unidad de riesgo; 1R = lo que pierdes si salta tu stop. "+0.5R" = ganaste la mitad de lo arriesgado.
- **Gate (G2):** puerta de aprobación que una regla debe pasar para avanzar.

---

# Resumen ejecutivo (10 líneas)

1. El proyecto es un laboratorio que prueba si reglas simples sobre NQ y ES ganan dinero real después de costos, con un proceso diseñado para no engañarse.
2. Tienes 10 años de datos de 1 minuto de NQ y ES (Databento), con la fuente por contrato pagada en `data/raw/databento_crudo/`; es el activo más valioso.
3. La idea de partida (rebotar en el máximo/mínimo de ayer) se probó con grids de cientos de combinaciones: los PF bonitos en entrenamiento (hasta 2.19) se caen a 0.29 en examen.
4. El único PF positivo documentado (1.63, NQ último año, VWAP, SL 80/TP 110) se eligió mirando ese mismo año, y no se replica.
5. La validación G2 (regla congelada, NQ 2016–21 y ES 2016–25) dio PF 0.76–0.94 con costos y salió "NO APROBADO".
6. LSR v1 (barrido de PDH/PDL con reversión) también fue rechazada: PF neto OOS 1.016 en NQ y 0.918 en ES, con límites inferiores del IC90 de 0.88 y 0.79.
7. Toda la rejilla de parámetros de LSR en NQ vale PF 0.99–1.00: es decir, ni siquiera ajustando se encuentra algo.
8. El placebo (niveles falsos de anteayer) rindió igual o mejor que los niveles reales (NQ 1.085 vs 0.998; ES 0.980 vs 0.898): no hay evidencia de que PDH/PDL importen.
9. Faltan en la carpeta los pre-registros y resultados de LSR/G2, la memoria del proyecto y el rastro de chats anteriores, y queda 1 commit local por subir con "Push origin".
10. El marco de subastas y el motor original quedan como herramientas; el README prohíbe dinero real hasta pasar los gates.
