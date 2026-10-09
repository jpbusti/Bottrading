# Resultado US100 ORB v2 (sin filtro de volumen), 2026-10-09

Pre-registro: `docs/PREREGISTRO_US100_ORB_V2.md` (redactado antes de correr). Codigo: `scripts/us100_orb/event_study_v2.py --sin-volumen`. Eventos: `resultados/us100_orb/event_study_v2_sinvol_eventos.csv`.
Datos y supuestos iguales a `docs/ESTUDIO_EVENTOS_US100_ORB.md` (USTEC 1m ET, 2018-2026, 2,182 dias, 670 excluidos). Unico cambio: sin filtro de volumen.

## Veredicto
**Sin edge y por debajo del minimo de eventos. Se detiene en la fase 1: no hay backtest, ni PF, ni walk-forward, ni placebos.** Eso es lo que fija el pre-registro v2 (reglas 2 y 4).

## Eventos
- **219 eventos en 8.8 anios** (122 largos, 97 cortos), contra los 300 exigidos. Con el pre-registro v1 eran 10. Quitar el volumen arregla la distribucion temporal (2018: 17, 2019: 23, 2020: 26, 2021: 26, 2022: 20, 2023: 24, 2024: 31, 2025: 27, 2026: 25) pero no alcanza el minimo.
- Sin exclusiones de calendario (FOMC/OPEX/NFP): 259 eventos, tampoco llega a 300.
- Embudo: ORB crudo 1,507 -> + VWAP 632 -> + retest 219. Hora de entrada: 10:xx 182, 11:xx 31, resto 6.

## Retorno forward (evento completo, baseline "post", diferencia pareada)
| Horizonte | n | Evento % | Baseline % | Dif. % | t | p unilateral | IC90 bootstrap dif. % |
|---|---|---|---|---|---|---|---|
| 30 m | 211 | +0.005 | -0.007 | +0.012 | 0.49 | 0.311 | [-0.033, +0.063] |
| 1 h | 210 | -0.018 | -0.007 | -0.011 | -0.35 | 0.635 | [-0.058, +0.056] |
| 2 h | 210 | +0.008 | +0.022 | -0.015 | -0.51 | 0.693 | [-0.054, +0.045] |
| Cierre | 211 | -0.027 | -0.018 | -0.009 | -0.30 | 0.619 | [-0.050, +0.057] |

- Ningun horizonte cumple la condicion (a) del pre-registro (p x 4 < 0.10); el menor p es 0.311 y todos los IC90 incluyen el cero. El retorno medio del evento es ~0 a todos los horizontes (+0.005% a 30 m contra un costo de 2.0 pts, ~0.013% con US100 en ~15,000).
- Baseline "literal" (sesgado a favor del baseline, informativo): diferencias negativas, de -0.03% a -0.06%, significativas a 1 h, 2 h y cierre. Tampoco hay edge por ahi.
- Sin calendario (259 eventos): diferencias +0.004% a 30 m, negativas en el resto, p >= 0.43.
- Etapas previas (baseline "post"): ORB crudo (1,507) y + VWAP (632) tienen diferencia ~0 y no significativa en los cuatro horizontes (p >= 0.32).

## Lectura
El "no funciona" de v1 era en parte falta de datos; con 219 eventos repartidos en todos los anios ya se ve que el ORB con VWAP y retest no se separa de un instante aleatorio de la misma hora y direccion. Con n = 211 el estudio detecta diferencias del orden de 0.05% a 30 m (dos errores estandar de la media de la diferencia; el error estandar es ~0.024%); si existiera un efecto de ese tamano o mayor, habria aparecido. Un efecto menor que el costo (~0.013%) no sirve de todos modos.

## Reporte en el formato del proyecto
| Item | Valor |
|---|---|
| PF neto | no calculado (no se paso a backtest) |
| IC90 inferior del PF | no calculado |
| Numero de trades | 219 eventos (no son trades simulados); minimo exigido 300 |
| Max drawdown | no calculado |
| Robustez (rejilla de parametros, sensibilidad temporal) | no ejecutada por la regla de parada; unica sensibilidad hecha: sin calendario (259 eventos), mismas conclusiones |

## Advertencias
Calendario manual (FOMC escrito a mano, NFP aproximado, CPI/PPI sin excluir). El estudio v2 se hizo sobre los mismos datos que v1 y las etapas ORB crudo y +VWAP ya se conocian; por eso el criterio de edge fue mas exigente (Bonferroni, IC90 > 0 y retorno por encima del costo).
Relajar el retest o la pendiente de VWAP para llegar a 300 eventos seria una hipotesis nueva (v3) sobre datos ya vistos y no se hizo.
