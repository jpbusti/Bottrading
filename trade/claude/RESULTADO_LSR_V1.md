# Resultado: auditoría PDH/PDL y backtest de Liquidity Sweep Reversal v1 (NQ/ES)

Fecha: 2026-10-08 (v2: NQ extendido a 10 años). Protocolo: PREREGISTRO_LSR_V1.md (escrito antes de correr). Evidencia: nivel A (datos propios, costos por año; costos [VERIFICAR] con broker).

## VEREDICTO: RECHAZADA (NQ y ES, 10 años)
| | n OOS | PF bruto | PF neto | IC90 PF inf. | Max DD (0.5% / 1%) | DD Monte Carlo p95 (0.5%) | Cumple |
|---|---|---|---|---|---|---|---|
| NQ A (2019-2026) | 901 | 1.05 | 1.016 | 0.877 | 4.3% / 8.7% | 16.0% | No (PF, IC90) |
| ES A (2019-2026) | 909 | 1.01 | 0.918 | 0.792 | 11.0% / 22.0% | 24.8% | No (PF, IC90) |
| NQ B (premercado, solo 2016-21) | 126 | 1.33 | 1.165 | 0.728 | 1.0% | 2.5% | Excluido |
| ES B (premercado) | 432 | 1.17 | 0.928 | 0.727 | 3.5% | 5.5% | Excluido |

- **Causa principal:** no hay edge bruto (PF bruto 1.01-1.05); los costos lo dejan en ≈1.0 o menos. El placebo (niveles de D-2) rinde igual o mejor que PDH/PDL reales (NQ 1.085 vs 0.998; ES 0.980 vs 0.898): los niveles no aportan información.
- **Hallazgo:** con SL/TP de 0.8-1.2 y 1.5-2.0 × ATR diario ~93% de las salidas son por cierre de sesión; es en la práctica "entrar tras el reclaim y mantener hasta el cierre". Por eso toda la rejilla k/m da el mismo PF.
- **Variante a iterar:** ninguna con evidencia. NQ ventana 10:00-11:30 (PF 1.015) no mejora; solo 9:45-12:00 da 1.015. Retomar PDH/PDL exige una hipótesis nueva pre-registrada.

## Fase 1: auditoría de estrategias PDH/PDL probadas
| # | Estrategia / reglas | Datos y timeframe | PF bruto / neto | n | IC90 PF inf. | Max DD | Sesgos | Estado |
|---|---|---|---|---|---|---|---|---|
| 1 | Marco de subastas Setup A: barrido + retest limit + VWAP, antes de 10:30, SL 80 / TP 110 pts | NQ 2025-10→2026-10, 1m | n/d / **1.63** (costo 3 pts) | 172 | n/d | n/d | Curve-fitting (24 variantes sobre 254 sesiones), fill por toque optimista, puntos fijos | **Rechazada** |
| 2 | Misma regla en años previos | NQ 2021-2025, 1m | n/d / 1.02-1.03 | n/d | IC incluye 0 | n/d | Continuo sin ajustar, puntos fijos | **Rechazada** |
| 3 | Regla normalizada G2 (ATR y %) | NQ 2016-21; ES 2016-25 | exp. bruta +0.03/+0.09 R / **0.76-0.94** | 577/579 (NQ), 926/925 (ES) | 0.67/0.73 (NQ), 0.70/0.84 (ES) | n/d | Contratos individuales, pre-registrado | **Rechazada** |
| 4 | Variantes de contexto (antes de 10:30, VAH/VAL, contra cierre previo) | NQ 5 años | n/d | n/d | n/d | n/d | Minería sobre la misma muestra | **Sin evidencia** |
| 5 | Motor original en src/ (PDH/PDL, ORB, VWAP + filtros) | yfinance ~60 días | sin cifras | n/d | n/d | n/d | Muestra insuficiente | **Sin evidencia** |

PF positivo documentado: solo la #1 (in-sample, nivel C). Activa hoy: el marco de subastas como herramienta visual, NO VALIDADO como sistema.

## Fase 2
LSR v1 no se había probado. El Setup A del marco es parecido pero entra con limit en retest, con VWAP y stops fijos.

## Fase 3: detalle
Walk-forward por fold (PF neto OOS): **NQ** 2019 0.94, 2020 1.23, 2021 1.11, 2022 0.90, 2023 1.16, 2024 0.87, 2025 1.25, 2026 0.75. **ES** 2019 0.66, 2020 1.46, 2021 0.97, 2022 0.80, 2023 1.01, 2024 0.84, 2025 0.81, 2026 1.11.
Subperíodos (WF-OOS; 2016-18 = combo central, sin OOS): NQ 0.93 / 1.10 / 0.96 / 1.00; ES 0.80 / 0.98 / 0.88 / 0.92 (2016-18, 2019-21, 2022-24, 2025-26).
Fragilidad: NQ sin un año se mueve 0.985-1.052 (sin dependencia de un solo año, pero porque el PF ronda 1.0); ES sin 2020 cae a 0.87.

| Prueba (combo central 1.0/1.75, toda la muestra) | NQ PF neto | ES PF neto |
|---|---|---|
| Base | 0.998 | 0.898 |
| Rejilla k/m (puntos PF ≥ 1.15) | 0 de 9 (0.991-1.004) | 0 de 9 (0.889-0.914) |
| Costos ×0.5 / ×2 | 1.021 / 0.954 | 0.953 / 0.798 |
| Reclaim N=3 / N=5 | 0.981 / 1.002 | 0.904 / 0.917 |
| Entrada en apertura siguiente | 0.999 | 0.900 |
| Solo 9:45-12:00 / solo 14:00-15:30 | 1.015 / 0.876 | 0.929 / 0.746 |
| Ventana 10:00-11:30 | 1.015 | 0.891 |
| Ventana prohibida 12:00-14:00 | 0.937 | 0.801 |
| Sin filtros de régimen/calendario | 0.973 | 0.894 |
| **Placebo (niveles D-2)** | **1.085** | **0.980** |
| Regla original traducida (0.179/0.247 ATR) | 1.031 | 0.825 |
| Estructural (SL al extremo del barrido, TP lado opuesto) | 0.883 | 0.741 |
IC90 inferior del PF (= percentil 5 del bootstrap) < 1.0 en todas las celdas relevantes: falla el estrés.

## Datos, desviaciones y sesgos
- **NQ:** 2016-10→2021-10 por contrato con premercado; 2021-10→2026-10 desde el continuo `NQ_databento_1m_10y_RTH` (c.0, RTH, sin ajustar). Contratos etiquetados por periodo de roll (el continuo cambia el día hábil siguiente al 3er viernes de mar/jun/sep/dic, verificado por saltos de apertura de 150-960 pts); se descartaron 4 días alrededor de cada roll (80 días) y los niveles nunca cruzan un cambio de contrato. Limitación: en la semana de vencimiento el contrato front es menos líquido que el real.
- Bloque B solo en NQ 2016-21 y ES (el continuo es RTH). Panamá no se usó: contratos individuales.
- El documento QRM calibraba 1.33×/1.83× ATR; la regla congelada equivale a 0.179×/0.247×. Se corrió la rejilla pedida (decide) y la equivalente (referencia).
- Spread del bloque B (<1.5 pts) no verificable con OHLCV; costos por año son supuestos [VERIFICAR]. No se excluyeron días completos de CPI/NFP/PPI (el bloque A arranca a 9:45); FOMC desde la lista de la Fed, con fechas extraordinarias 2019-20 [VERIFICAR].
- PF en R (riesgo igual por trade); en dólares con 1 contrato es parecido (NQ 0.97, ES 0.91 en el combo central).
- Sesgos propios: rejilla y sensibilidades sobre toda la muestra (descriptivas); el walk-forward elige combo solo con datos previos. SL antes que TP en la misma vela 1m; fill al cierre de la vela de reclaim sin impacto extra; ~60 sesiones iniciales perdidas por calentamiento del filtro ATR.
- Con SL ≈ 1 ATR diario un riesgo de 0.5% exige cuentas grandes (NQ ≈ $9,000 por contrato).
- Motor verificado: 6 trades de ES revisados contra los datos crudos (contrato, niveles, vela de reclaim) coinciden.

## Archivos
scripts/lsr/{extraer_contratos_ext.py, unir_nq.py, motor_lsr.py, run_lsr.py}; resultados/lsr/{resultado_lsr.log, trades_*, wf_oos_*}.
