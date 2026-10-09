# Fase 0: estudio de eventos US100 ORB (2026-10-09)

Pre-registro: `docs/PREREGISTRO_US100_ORB.md` (firmado). Codigo: `scripts/us100_orb/event_study.py`. Datos: USTEC IC Markets 1m -> 5m, 2018-01 a 2026-10 (NQ 10y RTH como contraste).
Salida completa: `resultados/us100_orb/event_study_{us100,nq}.csv`. No hay SL/TP ni costos: solo retorno forward direccional desde la apertura de la barra de entrada.

## Evento
Config.yaml: OR 09:30-09:45; ruptura = cierre fuera del OR; VWAP con pendiente a favor (5 barras); volumen de la barra de ruptura > 1.5x media de 20 barras; retest <= 6 barras;
entrada en la apertura siguiente, hasta 15:00. Horizontes: 30 min, 1 h, 2 h y cierre. Baselines: B1 misma hora en 5 dias sin evento; B2 5 barras del mismo dia. Estadistica pareada, t de Student y bootstrap por bloques de 20.

## Resultado US100 (unidad: ATR diario previo; entre parentesis, puntos)
| Evento (ablacion) | N | Dif. vs B1 a 2 h | t | Conclusion |
|---|---|---|---|---|
| ORB crudo | 2161 | +0.016 ATR (+1.9 pts) | 1.89 (p 0.059) | marginal, bajo el costo de 2.5 pts |
| + VWAP | 928 | +0.007 ATR | 0.60 | nada |
| + VWAP + volumen | 60 | -0.045 ATR | -0.87 | nada |
| **Completo (+ retest)** | **18** | -0.094 ATR (-8.9 pts) | -1.35 (1 h: t -2.9) | muestra inutil |

Contra B2 (mismo dia) ningun horizonte es positivo en ninguna variante. En NQ proxy: ORB crudo 2 h +0.017 ATR (p 0.038, no sobrevive a Bonferroni 0.05/4); completo 80 eventos, dif. +28 pts a 2 h, t 1.37, no significativo.

## Hallazgos
1. **El evento completo tiene 18 eventos en 8.8 anios** en US100 (80 en NQ). El criterio de aprobacion exige >= 300 trades: es inalcanzable con esta regla. El cuello es el filtro de volumen: solo 3.7% de las barras (6.6% de las rupturas) superan 1.5x la media de 20 barras (tick volume del CFD).
2. Ninguna etapa muestra retorno forward distinto del baseline con significancia tras corregir por multiples pruebas. El unico efecto (ORB crudo, 2 h, ~+0.016 ATR) es menor que el costo.
3. El bootstrap por bloques no es fiable con n < 60 (el bloque de 20 abarca casi toda la muestra); para n = 18 los IC de bloques son degenerados. Valen t y p de Student.

## Veredicto preliminar
**Sin edge detectable.** Con el pre-registro actual la hipotesis no se puede aprobar (N) ni hay senal de retorno anormal. Segun la regla de la Fase 0, se recomienda NO correr el backtest completo con estas reglas.
Cambiar el umbral de volumen o el retest despues de ver esto seria una hipotesis nueva (PREREGISTRO_US100_ORB_V2), con el aviso de que ya vimos estos datos.
