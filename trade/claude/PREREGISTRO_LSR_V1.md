# Pre-registro: Liquidity Sweep Reversal v1 (LSR v1), auditoría QRM

Escrito el 2026-10-08 ANTES de correr cualquier backtest de LSR v1. Evidencia: nivel C hasta reproducirse con costos.

## 0. Hallazgos previos que condicionan el diseño
- **Calibración del documento QRM:** dice que "80 pts equivalían a 1.33×ATR en 2016". Es cierto solo si 80 pts se aplicaran crudos en 2016 (ATR14 diario RTH de NQ en 2016 ≈ 54 pts → 1.48×). Pero la regla original se congeló con datos de 2025-10→2026-10, cuando el ATR14 medio era 445.9 pts: 80 pts = 0.179×ATR y 110 pts = 0.247×ATR. Aplicar ×0.179/×0.247 es la traducción fiel de la regla. La rejilla pedida (k 0.8-1.2, m 1.5-2.0) es ~5-7 veces más ancha: es una estrategia distinta (SL ≈ un rango diario completo; TP casi inalcanzable intradía).
- **Decisión:** se corre la rejilla pedida (decide la aprobación) y, solo como referencia, la regla original traducida (k=0.179, m=0.247) y una variante estructural (SL al extremo del sweep, TP al extremo opuesto del día previo). No se usa la calibración 1.33/1.83.
- **Datos:** NQ por contrato solo 2016-10→2021-10-08 (hay continuo c.0 desde 2021-10 sin identificar contrato). ES por contrato 2016-10→2026-10-07. Con esos datos NQ no puede cubrir 10 años: su veredicto solo puede ser "RECHAZADA" o "NO CONCLUYENTE", nunca "APROBADA", hasta bajar NQ 2021-2026 por contrato (~US$9, requiere OK).
- **Premercado:** los .zst crudos traen 24h para NQ 2016-2021 y ES 2016-2026; el Bloque B se puede probar con ellos. El spread (<1.5 pts) NO es verificable con velas OHLCV: se documenta y el filtro no se aplica.

## 1. Reglas (interpretaciones declaradas)
- Velas de 5 min construidas desde 1m del contrato operado (contrato del día D = mayor volumen RTH de D-1). PDH/PDL = máximo/mínimo RTH 9:30-16:00 ET de D-1 de ESE contrato; fijos todo el día (sin actualizar intradía).
- Sweep largo: la vela 5m hace mínimo < PDL con el cierre de la vela previa ≥ PDL (el precio venía de arriba). Reclaim: cierre de una vela 5m > PDL dentro de las siguientes N=4 velas (la propia vela del sweep cuenta). Sensibilidad N=3 y N=5. Corto: espejo con PDH.
- Entrada al cierre de la vela de reclaim (principal); variante: apertura de la siguiente.
- Máximo un trade por día y por bloque; mientras haya posición no hay nuevas señales. Salida por SL, TP o cierre de sesión (15:59 en bloque A; 9:29 en bloque B).
- SL/TP evaluados en velas de 1m; si en una misma vela toca ambos, se asume SL primero.
- Variante principal ATR: SL = k×ATR14(D-1), TP = m×ATR14(D-1), k∈{0.8,1.0,1.2}, m∈{1.5,1.75,2.0}. ATR14 diario RTH con rango verdadero (usa solo datos hasta D-1).
- Variante estructural: SL = extremo del sweep ∓ 1 tick, TP = extremo opuesto del día previo. Referencia calibrada: k=0.179, m=0.247.

## 2. Filtros de régimen y calendario
- ATR14(D-1) por debajo del percentil 10 de su historia expansiva (mínimo 60 días) → no operar.
- Sin operar: día de roll (día en que cambia el contrato dominante), OPEX mensual (tercer viernes), días de decisión FOMC (calendario de la Fed, federalreserve.gov, incluidas llamadas no programadas de 2019-10-04 y 2020-03-02/03 y 2020-03-15→16 [VERIFICAR horas exactas]; se excluye la votación por notación 2025-08-22), sesiones cortas (menos de 350 velas RTH). Festivos: no hay datos.
- CPI/NFP/PPI: se publican 8:30 ET; el bloque A empieza 9:45, por lo que "primeros 15 min" y 9:30-9:45 quedan excluidos por construcción. No se cargó calendario de estos datos [limitación: sin exclusión de días completos].
- Ventanas bloque A (por hora de entrada, cierre de la vela de reclaim): 9:45-12:00 y 14:00-15:30 ET. Bloque B: 4:00-9:30 con volumen de la vela de sweep > 1.5× media de las 20 velas 5m previas y reclaim por cierre; spread no verificable.

## 3. Costos por año (puntos ida y vuelta) [VERIFICAR con broker]
Slippage 1 tick por lado + spread + comisión/fees $4.50 ida y vuelta.
- NQ: 2016-2019 = 0.50+0.50+0.225 = 1.225; 2020 = 0.50+0.75+0.225 = 1.475; 2021-2026 = 0.50+0.375+0.225 = 1.10.
- ES: 2016-2019 y 2021-2026 = 0.50+0.25+0.09 = 0.84; 2020 = 0.50+0.375+0.09 = 0.965.
- Estrés ×2 informativo.

## 4. Validación
- Walk-forward expansivo: entrenar 2016→Y-1, probar Y (Y=2019…2026). En entrenamiento se elige (k,m) por mayor PF neto con ≥30 trades (si no, centro k=1.0, m=1.75). OOS agrupado de todos los folds = base de la decisión.
- Subperíodos: 2016-2018, 2019-2021, 2022-2024, 2025-2026. Fragilidad: PF agrupado sin un año cae bajo 1.15 o baja >0.10.
- Robustez: rejilla k/m completa (curve-fitting si solo 1 punto ≥ 1.15), bootstrap de trades (percentil 5 del PF), sensibilidad a N, entrada en la apertura siguiente, ventanas horarias alternativas y costos ×2.
- Capital: riesgo por trade 0.5% (y 1%) con R-múltiplos aditivos; DD% = DD en R × riesgo.

## 5. Criterio de aprobación (por instrumento, sobre el OOS agrupado)
PF neto ≥ 1.15, IC90 inferior del PF > 1.0 (bootstrap 5,000), ≥ 300 trades, DD máximo < 20%. Bloque B solo entra si cumple lo mismo por sí solo. Si no cumple: RECHAZADA, sin ajustar parámetros.

## 6. Limitaciones declaradas
- Fill al cierre de la vela de reclaim sin impacto adicional. Los 3 filtros macro no son exhaustivos. Con SL de un ATR diario, una cuenta pequeña no puede dimensionar el riesgo 0.5% (p. ej. NQ ≈ $9,000 de riesgo por contrato).
