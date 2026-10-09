# Pre-registro: US100 ORB filtrado (VWAP + volumen + retest)

- **Fecha de redaccion:** 2026-10-09
- **Firma:** Juan, 2026-10-09 (confirmacion en el hilo del proyecto). Parametros fijados el 2026-10-09; no se cambian despues de ver resultados.
- **Pendientes menores sin confirmar expresamente (se mantienen los valores del config):** inicio de datos 2018-01-01 (igual que US100 v1), tolerancia del retest 0 pts, ventana de volumen de 20 barras continuas entre sesiones, riesgo por trade 0.5% para convertir DD en %.
- **Orden de fases:** Fase 0 (estudio de eventos, `scripts/us100_orb/event_study.py`) antes del backtest completo. Si no hay edge significativo, la hipotesis se descarta.
- **Relacion con US100 v1:** estrategia distinta (5m, ATR diario, retest). US100 v1 (`docs/PREREGISTRO_US100_V1.md`, H1 ORB sin retest en 1m) ya
  se corrio y no fue aprobada; este pre-registro no la reabre ni reutiliza sus resultados para elegir parametros.

## Hipotesis
Un Opening Range Breakout en US100 que ademas cumple (a) VWAP con pendiente a favor, (b) volumen de la barra de ruptura > 1.5x la media de 20 barras
y (c) retest confirmado del nivel roto, tiene expectativa neta positiva despues de costos.

## Logica de mercado (quien esta al otro lado)
Al abrir, ordenes de stop de traders que fadean el rango y de quienes cubren posiciones nocturnas quedan sobre/bajo el OR. Una ruptura con volumen
alto y VWAP a favor suele ser flujo informado/institucional; quien esta al otro lado son los que fadean el rango (vendedores de la ruptura) y se equivocan cuando
el flujo continua. El retest filtra rupturas de baja conviccion: solo se entra cuando el nivel roto se sostiene como soporte/resistencia. Si el flujo no persiste
(la mayor parte de las rupturas en un indice mean-reverting intradia), la regla no tiene edge: es lo que se prueba.

## Reglas exactas (identicas a `scripts/us100_orb/config.yaml`)
| Elemento | Regla |
|---|---|
| Instrumento / datos | US100 (CFD USTEC, IC Markets, velas 1m desde 2018-01-01) agregadas a 5m; NQ solo como proxy secundario (`--fuente nq`) |
| Sesion | RTH 09:30-16:00 ET (hora MT5 = ET + 7). Salida forzada al cierre de la barra de 15:55. Ultima entrada: barra de 15:00 |
| Opening Range | maximo/minimo de 09:30-09:45 (3 barras) |
| Ruptura | primera barra posterior al OR cuyo CIERRE esta fuera del OR; largo arriba, corto abajo |
| Filtro VWAP | VWAP de sesion (precio tipico x volumen) con pendiente a favor: VWAP[t] - VWAP[t-5 barras de 5m] > 0 largo / < 0 corto |
| Filtro volumen | volumen de la barra de ruptura > 1.5 x media de las 20 barras previas (continuas entre sesiones) |
| Filtro retest | dentro de 6 barras de 5m una barra toca el nivel roto (tolerancia 0 pts) y cierra del lado de la ruptura; si antes cierra dentro del OR, no hay trade |
| Entrada | apertura de la barra siguiente a la confirmacion; un trade como maximo por dia |
| ATR | ATR(14) diario RTH con datos hasta D-1 para SL/TP y filtros de regimen. ATR(14) de 5m solo para filtros intradia opcionales (ninguno activo) |
| SL / TP | SL = k x ATR, TP = m x ATR (precio fijo al entrar). Si SL y TP tocan en la misma barra, cuenta SL |
| Costos | spread IC Markets US100 1.0-1.5 pts (base 1.5, el maximo), comision 0, slippage 0.5 pts/lado => costo por trade 2.0-2.5 pts (base 2.5); sensibilidad con spread 1.0 (2.0 pts) y 3.0 (4.0 pts) |
| Riesgo | R = (pnl - costo) / SL. Max DD en % = DD en R x 0.5% de riesgo por trade |

## Rejilla de parametros (robustez)
k (SL) en {0.8, 1.0, 1.2} x m (TP) en {1.5, 1.75, 2.0} = 9 puntos. Combo central (1.0, 1.75). La rejilla NO elige el parametro final: decide robustez.

**Rejilla de robustez de los parametros de senal** (un parametro a la vez, `run_robustez.py`): pendiente VWAP {3, 5, 10} barras; barras de retest {4, 6, 8}; ultima entrada {14:30, 15:00, 15:30}. Valor base: 5 / 6 / 15:00.

## Criterio de aprobacion (todos, sobre el combo central salvo donde se indica)
1. PF neto >= 1.15.
2. IC90 inferior del PF (bootstrap por dia) > 1.0.
3. >= 300 trades.
4. Max drawdown < 20% (con la conversion de R a % indicada arriba).
5. Supera los tres placebos (abajo).
6. Rejilla: los 9 puntos con PF >= 1.15 e IC90 inferior > 1.0 (criterio de `validacion.atr_grid.rejilla`).
7. Walk-forward expansivo por anio (2019 en adelante, min. 30 trades en entrenamiento): PF OOS > 1 en todos los folds, IC90 inferior del PF OOS agrupado > 1.0.
8. Sensibilidad temporal: excluir cada anio no cambia el PF mas de 0.05 y el resultado no depende de un solo anio. Costo con spread 3.0 pts: PF > 1. Rejilla de parametros de senal: la conclusion no cambia entre los valores vecinos.

## Placebos
- **Timing aleatorio:** mismos dias, barra de entrada y direccion al azar (200 sorteos); p <= 0.05.
- **Direccion invertida:** misma senal re-simulada en sentido contrario; el PF real debe superar al invertido.
- **Niveles de otros dias:** OR de hace 2, 3, 5 y 10 dias aplicado al dia operado; el PF real debe superar a todos.

## Reglas de proceso
Sin cambios de parametros despues de ver resultados. Un resultado negativo se publica igual en `docs/RESULTADO_US100_ORB.md`.
Validacion con `validacion/` sin modificarlo.
