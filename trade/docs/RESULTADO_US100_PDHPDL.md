# Resultado: US100 PDH/PDL (reversion a la apertura de NY)

- **Fecha:** 2026-10-09. Pre-registro: `docs/PREREGISTRO_US100_PDHPDL.md` (commiteado antes de correr; parametros sin cambios).
- **Veredicto: NO APROBADA.** Falla en US100 el PF minimo, el IC90, la rejilla, el walk-forward y los tres placebos. NQ (proxy) es peor.
- **Datos:** USTEC 1m limpio 2018-01 a 2026-07 (2182 dias RTH validos). NQ front-month v2 2016-2026 (2491 dias). Costo base 2.5 pts por trade (spread 1.5 + 0.5 por lado).

## Reporte obligatorio (US100, combo central SL 0.75 ATR / TP 0.75 ATR)
| Metrica | Valor | Umbral |
|---|---|---|
| PF neto | **0.916** | >= 1.15 |
| IC90 del PF (bootstrap por dia) | **[0.787, 1.063]**, inferior 0.787 | inferior > 1.0 |
| Trades | 668 (374 cortos en PDH, 296 largos en PDL; 670 senales) | >= 300 |
| Win rate / expectativa | 46.6% / -0.022 R por trade | |
| Max drawdown | 32.0 R = 16.0% (a 0.5% de riesgo por trade) | < 20% |
| Robustez, rejilla k x m (9 puntos) | PF 0.883 a 0.956; ningun punto >= 1.0; IC90 inferior de 0.744 a 0.827 | 9/9 con PF >= 1.15 |
| Robustez temporal (excluir cada anio) | PF 0.878 a 0.966, estable; pero por anio: 2021-2023 PF 0.65-0.70, 2018-2020 y 2024/2026 PF 1.1-1.27, 2025 0.94 | |

PF por anio: 2018 1.17, 2019 1.10, 2020 1.27, 2021 0.70, 2022 0.67, 2023 0.65, 2024 1.13, 2025 0.94, 2026 1.11. Sin un solo anio decisivo, pero sin consistencia: resultado compatible con ruido alrededor de un PF menor a 1.

## Walk-forward (expansivo por anio, 2019-2026, 8 folds)
PF OOS por fold: 2019 1.12, 2020 1.16, 2021 0.58, 2022 0.67, 2023 0.80, 2024 1.21, 2025 1.02, 2026 0.93. Solo 4 de 8 folds superan 1.0. Agrupado: n=590, PF 0.884, IC90 [0.760, 1.029], max DD 41.5 R. Falla.

## Placebos (combo central)
| Placebo | PF real | PF placebo | Supera |
|---|---|---|---|
| Nivel (PDH/PDL de hace 2, 3, 5, 10 dias) | 0.916 | 0.686, 0.867, 0.927, **1.341** | No (el nivel de hace 10 dias rinde mas) |
| Timing aleatorio (200 sorteos) | 0.916 | mediana 0.915, p95 1.053; p = 0.50 | No |
| Direccion invertida (re-simulada) | 0.916 | 0.952 | No |

El resultado real es indistinguible de entrar en horas y direcciones al azar: los niveles del dia anterior no aportan informacion medible a este diseno.

## Costos
- Estres (spread 3.0, 4.0 pts por trade): PF 0.879. Sigue < 1.
- Costo por anio con el spread mediano observado en el CSV (2.0 pts en 2018-2023, 1.8 en 2024, 1.9 en 2025-2026): PF 0.929; por anio 2018 1.20, 2019 1.13, 2020 1.28, 2021 0.71, 2022 0.68, 2023 0.66, 2024 1.15, 2025 0.95, 2026 1.12. `cost_model` no guarda historico por anio, por eso se uso el spread observado.
- Los costos no explican el fracaso: con SL ~ 0.75 ATR (cientos de puntos) 2.5 pts son una fraccion minima del riesgo; la expectativa bruta ya es ~0.
- 75% de los trades terminan por salida de tiempo (502 de 668), 87 por TP y 79 por SL: con k y m de 0.5 a 1.0 ATR diario, el precio rara vez llega a SL/TP antes del cierre.

## Sensibilidad de senal (un parametro a la vez, PF central)
Ultima entrada 14:00: 0.928; 15:00: 0.916; 15:30: 0.905. Sin exigir cierre de rechazo (tocar PDH/PDL basta, 2093 trades): 0.870. Ninguna variante supera 1.0.

## Proxy NQ (informativo)
668 -> 764 trades, PF 0.824, IC90 inferior 0.718, max DD 22.4%, rejilla 0.79-0.86, walk-forward OOS PF 0.823 (IC90 inferior 0.70), placebos 0/3 (invertir la direccion da PF 1.01). Consistente con US100: sin edge.

## Conclusion
Con datos nuevos (2018-2026), costos reales de CFD y validacion completa, la reversion en PDH/PDL no tiene edge operativo: coincide con el antecedente de NQ en un ano de Databento. Que el precio "se vea" revertir en el grafico al tocar un maximo o minimo previo no se traduce en expectativa positiva medible, porque muchos toques siguen de largo y los que revierten no compensan, y entrar en cualquier hora al azar rinde lo mismo.

No se reabre esta hipotesis cambiando parametros sobre estos mismos datos (seria sobreajuste). Si se quiere seguir, necesitaria una hipotesis distinta y pre-registrada: por ejemplo ruptura (no reversion) de PDH/PDL con confirmacion, o PDH/PDL solo en dias de gap o de rango previo extremo.

## Reproducir
`python scripts/us100_pdhpdl/run_backtest.py | run_walkforward.py | run_placebo.py | run_robustez.py [--fuente nq]` desde `trade/`. Salidas en `resultados/us100_pdhpdl/`.
