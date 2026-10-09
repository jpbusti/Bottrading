# Estudio de eventos US100 ORB (v2), 2026-10-09

Reemplaza a `docs/informes/EVENT_STUDY_US100_ORB.md`. Pre-registro: `docs/PREREGISTRO_US100_ORB.md`. Codigo: `scripts/us100_orb/event_study_v2.py`.
Datos: solo `data/raw/us100/USTEC_1m_clean_2018_2026.csv` (ET, tick_volume como volumen), agregado a 5m RTH. Sin backtest, sin SL/TP, sin costos, sin optimizar parametros.
Salida: `resultados/us100_orb/event_study_v2_eventos.csv` (los 10 eventos con sus retornos).

## Evento y supuestos
- OR 09:30-09:45; primera barra de 5m posterior cuyo cierre queda fuera del OR (hasta la barra de las 15:00); volumen de esa barra > 1.5 x media de las 20 barras previas (continuas entre sesiones); VWAP de sesion (precio tipico x tick volume) en la barra de ruptura vs 5 barras antes; retest en <= 6 barras: una barra toca el nivel (tolerancia 0) y cierra del lado de la ruptura. Si la barra que toca cierra del lado equivocado, el evento se invalida.
- **Entrada = cierre de la barra de retest** (precio de cierre). Un evento como maximo por dia.
- Retorno forward direccional en %. Horizontes 30 m, 1 h, 2 h (6/12/24 barras) y cierre de las 16:00. Si el horizonte pasa de las 16:00, ese evento no cuenta en ese horizonte (n baja).
- **Dias ignorados (670 de 2,182):** gap de apertura > 1% (392, medido contra el cierre RTH del dia anterior), OPEX = 3er viernes (101), NFP aproximado como 1er viernes (99), FOMC (70), ATR(14) diario < percentil 10 de su historia previa (48, percentil expansivo sin look-ahead), sin ATR (14), sesion incompleta o media (4; el cargador ya descarta antes las < 70% de barras).
- **[VERIFICAR] calendario:** no hay calendario economico en el repo. Las fechas FOMC estan escritas a mano; NFP se aproxima por 1er viernes (hay excepciones); **CPI y PPI no se excluyeron** (no hay fuente de fechas). Sensibilidad sin ninguna exclusion de calendario (FOMC/OPEX/NFP): 15 eventos, mismas conclusiones.
- **Baseline (modificacion respecto a la letra del encargo).** 1000 sorteos por evento, misma fecha y misma hora ET de la entrada, misma direccion. Si se sortean todas las barras de esa hora, las barras anteriores a la ruptura tienen en su ventana forward el propio movimiento de la ruptura, en la direccion del evento: sesgo del baseline. Por eso el baseline **principal** sortea solo barras de esa hora **posteriores a la barra de entrada** ("post"); la version literal ("literal") se reporta tambien y da lo mismo.
- Estadistica: diferencia pareada por evento (evento menos media de los 1000 sorteos); t de Student con p unilateral (diferencia > 0); bootstrap por bloques de eventos consecutivos, 5000 remuestras, bloque = min(20, n/4) = 2 eventos [con n = 10 el IC es poco fiable].

## 1. Eventos
**10 eventos en 8.8 anios: 4 largos y 6 cortos.**
- Por anio: 2018: 2, 2019: 7, 2025: 1. Ninguno en 2020-2024 ni en 2026.
- Por hora ET de entrada: 10:00 a 10:59 -> 9; 11:00 a 11:59 -> 1.
- Embudo (con exclusiones): ORB crudo 1,507 -> + VWAP 632 -> + volumen 40 -> + retest 10.
- **Hallazgo sobre el filtro de volumen:** la fraccion de barras con volumen > 1.5x la media de 20 barras cae de 6.6-9.9% (2018-2019) a 0.2-2.2% (2022-2026). El tick volume de USTEC no es estacionario (media por barra 622 en 2019, 2,018 en 2025), asi que el umbral relativo casi no se dispara despues de 2019. Los 10 eventos son casi todos de 2018-2019.

## 2. Retorno forward y significancia (evento completo, n = 10; baseline "post")
| Horizonte | n | Evento % | Baseline % | Dif. % | t | p (unilateral) | IC90 bootstrap dif. % |
|---|---|---|---|---|---|---|---|
| 30 m | 10 | +0.015 | -0.164 | +0.179 | 2.73 | **0.012** | [+0.108, +0.242] |
| 1 h | 10 | -0.200 | -0.167 | -0.033 | -0.73 | 0.759 | [-0.095, +0.026] |
| 2 h | 10 | -0.209 | -0.170 | -0.039 | -0.64 | 0.731 | [-0.122, +0.025] |
| Cierre | 10 | -0.218 | -0.218 | +0.001 | 0.02 | 0.493 | [-0.028, +0.029] |

Version literal del baseline: 30 m dif. +0.129%, p 0.021; 1 h, 2 h y cierre sin significancia (p 0.74, 0.79, 0.45). Sin exclusiones de calendario (n = 15): 30 m dif. +0.131%, p 0.046; el resto no significativo.
Informativo, evento contra cero: el retorno medio es +0.015% a 30 m (t 0.31, no significativo), -0.200% a 1 h (t -2.35, p bilateral 0.043), -0.209% a 2 h y -0.218% al cierre. El evento no gana dinero por si mismo.
Etapas anteriores (informativo, baseline "post"): ORB crudo (1,507 eventos), + VWAP (632) y + VWAP + volumen (40) tienen diferencia con el baseline ~0 y no significativa en los cuatro horizontes (|t| < 0.7). Con el baseline "literal" esas mismas etapas salen con diferencias fuertemente negativas (ORB crudo: baseline +0.145% a 30 m, t -21), que es el sesgo descrito arriba y confirma por que no se usa como principal.

## 3. Veredicto
**Criterio literal del encargo (p < 0.10 y dif. > 0 en al menos un horizonte): se cumple en 30 m (p 0.012, tambien tras Bonferroni 0.025), asi que formalmente "edge: si".** No lo considero un edge utilizable:
1. n = 10 (7 de ellos en 2019); un solo horizonte, y 1 h, 2 h y cierre son nulos o negativos.
2. La diferencia positiva viene de un baseline negativo (-0.16%), no de que el evento rinda: su retorno a 30 m es +0.015%, igual que cero y menor que el costo de un trade (2.0 pts ~ 0.03% con US100 en ~7,000 en 2018-2019).
3. El retorno del evento es significativamente negativo a 1 h (p 0.043).
4. El pre-registro exige >= 300 trades; con la regla firmada hay 10 (tasa ~1 por anio). Imposible de alcanzar.
**Decision: no pasar al backtest con estas reglas.** Cambiar el umbral de volumen o el retest despues de ver esto seria una hipotesis nueva (v2 del pre-registro), sobre datos ya vistos.

## 4. Siguiente hipotesis propuesta
1. **ORB sin filtro de volumen relativo, o con el volumen normalizado por hora del dia** (el 1.5x sobre 20 barras no es estable por la deriva del tick volume). Con + VWAP + retest habria cientos de eventos y se podria medir.
2. VWAP mean reversion intradia: desviaciones del VWAP (en ATR) con vuelta a la media; el ORB crudo y + VWAP tienen retorno ~0 y no baten al baseline; en los 10 eventos completos el retorno a 1 h y 2 h es negativo, algo que solo sugiere reversion con n = 10.
3. ATR trend: continuacion tras dias de rango amplio/ATR alto, con tendencia de VWAP.
Cada una requiere pre-registro propio y, antes del backtest, otro estudio de eventos con n >= 300.
