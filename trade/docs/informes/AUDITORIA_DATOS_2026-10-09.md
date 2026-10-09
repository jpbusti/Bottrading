# Auditoría de datos NQ — 2026-10-09

Alcance: solo lectura de los archivos locales. No se descargó nada, no se corrió ningún backtest, no se tocó IBKR.
Las cifras salen de leer los archivos con pandas (no de los reportes antiguos). Lo no verificable lleva **[VERIFICAR]**.

## 1. `data/raw/NQ_databento_1m_10y_RTH.csv.gz`

| Pregunta | Respuesta |
|---|---|
| Horario | **Solo RTH**: 09:30:00 → 15:59:00 ET (velas de 1 min, 7 horas-reloj: 09:xx a 15:xx). Nada de premercado ni ETH. |
| Rango | min `2016-10-10 09:30:00-04:00` · max `2026-10-06 15:59:00-04:00` |
| Filas | **981 600** (2 556 sesiones; 90 con menos de 390 velas = medios días de bolsa: 58 de 210 velas, 21 de 225) |
| Tipo de contrato | **Continuo `NQ.c.0` (roll por calendario), SIN ajustar.** No hay columna de símbolo. Los saltos de roll están dentro de los datos: el lunes tras el 3er viernes de mar/jun/sep/dic el open difiere del cierre previo en decenas a cientos de puntos (p. ej. 2024-12-23 +508, 2025-12-22 +763). No es back-adjusted ni contrato individual. |
| Calidad | 0 timestamps duplicados, ordenado, 0 volúmenes = 0, 0 precios ≤ 0, OHLC coherente (reporte previo), 4 huecos intradía de 5-60 min, ninguno > 30 min. |

**Hallazgo 1 (reporte desactualizado).** `data/raw/calidad/reporte_calidad_NQ_2021_2026.txt` describe este archivo como 486 175 velas (2021-10-11 → 2026-10-06). Hoy el archivo tiene 981 600 filas desde 2016-10-10. 486 175 + 495 425 (filas de `NQ_databento_1m_2016_2021_RTH` según `reporte_calidad_validacion.txt`) = 981 600, así que el archivo es la **concatenación de dos descargas c.0** (2016-10→2021-10 y 2021-10→2026-10). Ninguno de los scripts del repo genera esa unión **[VERIFICAR quién y cómo la hizo]**; hay que regenerar el reporte de calidad sobre el archivo actual.

**Hallazgo 2 (dos usos distintos de NQ).** LSR v1 (RESULTADO_LSR_V1.md, línea 53) usó 2016-21 *por contrato* (desde el `.zst` crudo, con premercado) y 2021-26 desde este c.0. Este `.csv.gz` completo es c.0 en los 10 años, así que **no reproduce idéntico** lo que vio LSR v1 en 2016-21. Para nuevos backtests hay que decidir una sola fuente por tramo y documentarla.

## 2. `data/raw/NQ_databento_1m.csv`

| Pregunta | Respuesta |
|---|---|
| Horario | **ETH casi completo**, velas de 1 min en horas ET 18-23 y 00-16 (**sin hora 17**: pausa diaria 17:00-18:00 ET). Incluye domingos por la noche. Cubre sesión asiática, europea y RTH. |
| Rango | min `2025-10-06 20:00:00-04:00` · max `2026-10-06 19:59:00-04:00` (≈ 1 año) |
| Filas | **350 561** (314 fechas; 260 saltos > 60 min = fines de semana y festivos; 46 saltos de 5-60 min [VERIFICAR su causa]) |
| Tipo de contrato | Mismo **continuo c.0 sin ajustar**: las 97 470 velas RTH en común con el `.csv.gz` coinciden (diferencia de cierre = 0.0). Roll visible en dic-2025, mar-2026, jun-2026, sep-2026. |
| Desglose por sesión | 18:00-03:00 ET: 138 224 velas · 03:00-09:30 ET: 100 180 · RTH 09:30-16:00: 97 470 · 16:00-17:00: 14 687 |

## 3. ¿Tengo sesión asiática (18:00-03:00 ET) y europea (03:00-09:30 ET)?

**Sí, pero con un hueco de 4 años.** Archivos que contienen ETH:

| Tramo | Dónde | Estado |
|---|---|---|
| 2016-10-09 → 2021-10-08 | `data/raw/databento_crudo/NQ_databento_1m_2016_2021_RTH.csv.zst` (2 353 506 filas, 24 h, **por contrato**: 83 símbolos, 58 son spreads calendario `NQH0-NQM0` que hay que excluir) | Disponible. A pesar del nombre "RTH" contiene 18:00-17:00 ET. Hay que filtrar outrights `^NQ[FGHJKMNQUVXZ]\d$` y elegir contrato (ver `scripts/lsr/extraer_contratos_ext.py`, que hoy solo extrae 04:00-16:00). |
| **2021-10-08 → 2025-10-06** | — | **FALTA** (~4 años de ETH) |
| 2025-10-06 → 2026-10-06 | `data/raw/NQ_databento_1m.csv` | Disponible (c.0). |

Mezclar el tramo 1 (por contrato) con el tramo 3 (c.0) exige unificar la regla de roll **[VERIFICAR]**.

**Comando para consultar el costo del hueco SIN descargar** (la API de metadata es de consulta; necesita `DATABENTO_API_KEY`, que en esta sesión **no está configurada**, así que no pude obtener la cifra):

```python
import os, databento as db
c = db.Historical(os.environ["DATABENTO_API_KEY"])
usd = c.metadata.get_cost(dataset="GLBX.MDP3", symbols=["NQ.c.0"], stype_in="continuous",
                          schema="ohlcv-1m", start="2021-10-08", end="2025-10-06")
print(usd)   # solo consulta; no descarga
```

Costo estimado: **[VERIFICAR — correr el comando]**. Referencia interna, no precio: `descargar_databento_5anios.py` fijó un tope de seguridad de USD 12 para 5 años de NQ.c.0 `ohlcv-1m` de 24 h, lo que sugiere que el hueco de 4 años queda en el mismo orden, pero no hay un costo real registrado en el repo.

Para descargarlo, el script ya existente `scripts/descarga/descargar_validacion.py` hace tramos de 6 meses con reintentos, pero **filtra a 09:30-16:00**; habría que quitar ese filtro (o guardar 24 h). No lo modifiqué ni lo ejecuté.

## 4. Volume Profile (VAH / VAL / POC)

- **¿Se puede con 1 min?** Sí, como aproximación. Se reparte el volumen de cada vela entre los niveles de precio de su rango [Low, High] (uniforme, o concentrado en el cierre/precio típico) en bins de 1-2 puntos, y se calcula POC (bin de mayor volumen) y el Value Area del 70 % alrededor del POC.
- **Precisión esperada:** la vela de 1 min en NQ tiene rango mediano de **7.0 pts** (media 9.3, p90 19.5; medido en el archivo). El volumen real dentro de la vela no se conoce, así que el error de POC/VAH/VAL es del orden de unos pocos puntos y depende del método de reparto; el POC puede saltar entre dos nodos cercanos. **Magnitud exacta: [VERIFICAR]** comparando contra un perfil de ticks de una muestra (p. ej. 1-2 meses) antes de confiar en niveles a precisión de tick. Para estrategias con stops de decenas de puntos puede bastar; para niveles "exactos" no.
- **¿Hace falta tick?** Solo para validar la aproximación o si el estudio exige precisión < ~5 pts. Opción más barata antes que ticks: `ohlcv-1s`. Costo de 10 años en `trades` y en `ohlcv-1s`: **[VERIFICAR]** — consultar con `get_cost` (mismo snippet, `schema="trades"` o `"ohlcv-1s"`, `start="2016-10-10"`, `end="2026-10-07"`). No estimo cifras sin esa consulta.
- Advertencia: el perfil debe calcularse **dentro de un mismo contrato** (los datos son c.0 sin ajustar; un perfil que cruce un roll mezcla niveles separados por la prima de carry).

## 5. WOR y DOR

| Nivel | Qué hace falta | ¿Lo tengo? |
|---|---|---|
| **DOR** (rango de apertura del día) versión RTH (p. ej. 09:30-10:00 ET) | Solo velas 1 min RTH | **Sí**, 10 años (`NQ_databento_1m_10y_RTH.csv.gz`). |
| **DOR** versión Globex (apertura 18:00 ET) | ETH, velas 18:00+ | Solo 2016-21 (`.zst`) y 2025-26 (`NQ_databento_1m.csv`). Falta 2021-10→2025-10. |
| **WOR** versión RTH (lunes 09:30) | Velas RTH del lunes | **Sí**, 10 años. |
| **WOR** versión Globex (domingo 18:00 ET) | Velas del domingo por la noche | Solo 2016-21 y 2025-26. Falta el hueco. |

Definir cuál es el "día/semana" de referencia (RTH vs Globex) es una decisión de diseño que el CFD US100 también condiciona: el cierre y la apertura del CFD en el bróker **[VERIFICAR con las horas de trading del bróker]**.

## 6. Inventario

**Listos para usar (con las limitaciones indicadas)**
- `NQ_databento_1m_10y_RTH.csv.gz` — RTH 2016-10→2026-10, c.0 sin ajustar. Listo para estudios RTH (PDH/PDL, DOR RTH, WOR RTH, AVWAP anclado en RTH, perfil aproximado). Dataset oficial recomendado para el próximo backtest RTH, **usando solo niveles dentro del mismo contrato** (excluir/etiquetar los días de roll, como hizo LSR v1: roll = lunes tras el 3er viernes).
- `NQ_databento_1m.csv` — ETH 1 año (2025-10→2026-10). Listo solo para pruebas con sesiones asiática/europea de ese año.
- `ES_databento_1m_10y_RTH.csv.gz` — ES RTH 10 años (no auditado en detalle: fuera del alcance NQ; el reporte previo indica 989 804 velas, 2016-10-10 → 2026-10-07).

**Hay que verificar**
- Origen/unión del `.csv.gz` de 10 años (hallazgo 1) y regenerar `calidad/reporte_calidad_*` para el archivo actual.
- Volumen: se asume que `Volume` del c.0 es el del contrato front (no del más líquido) [VERIFICAR]; semana de vencimiento con menor liquidez (ya señalado en RESULTADO_LSR_V1).
- 46 saltos de 5-60 min en el ETH y 4 en el RTH (causa no revisada).
- Regla de roll distinta entre `.zst` (por contrato) y c.0 si se unen.
- `NQ_1d.csv` (2015-01-02 → 2026-10-08, 2 960 filas) y `NQ_1h.csv` (2024-05-16 → 2026-10-07, 3 559 filas): columnas estilo Yahoo (`Adj Close`), fuente distinta a Databento. No mezclar con los datos de 1 min **[VERIFICAR origen]**.

**Faltan (para el plan de Auction Market Theory completo con sesiones globales)**
- NQ ETH 2021-10-08 → 2025-10-06 (4 años). Costo: **[VERIFICAR con `get_cost`, ver §3]**.
- Opcional, solo si se exige precisión de perfil: `trades`/`ohlcv-1s`. Costo: **[VERIFICAR]**.

## 7. ¿Se puede validar el plan Auction Market Theory (PDH/PDL + VAH/VAL + POC + AVWAP) con los datos actuales?

**Sí, la versión RTH** (con 10 años y sin comprar nada). **No** la versión que usa sesiones asiática/europea para 2021-10→2025-10 (hueco ETH).

Cambios en el motor:
1. **Motor nuevo, no modificar `motor_lsr.py`.** Ese motor está congelado por el pre-registro LSR v1 (bloques A/B, velas 5m, ATR fijo). Conviene un `scripts/amt/motor_amt.py` que **reutilice** `validacion/` (costos, walk-forward, placebo, IC90) y el patrón `Mercado`/`Dia` de `motor_lsr.py` (día por contrato).
2. **Perfil de volumen:** módulo que calcula por sesión POC/VAH/VAL desde 1 min con bins parametrizables (ver §4), siempre dentro de un contrato.
3. **AVWAP:** se calcula directo con OHLCV de 1 min: Σ(precio típico × volumen)/Σ volumen desde el ancla. Ojo con anclas que crucen un roll (usar el contrato del día).
4. **DOR/WOR:** ver §5; versión RTH disponible hoy.
5. **Pre-registro antes de mirar datos** (metodología del proyecto) y placebo/walk-forward con costos del modo CFD.

## 8. Siguiente paso concreto

1. Correr el snippet de `get_cost` (§3 y §4) con tu API key — consulta, sin descargar — y pegar los números aquí.
2. Regenerar el reporte de calidad del `.csv.gz` de 10 años y fijar la regla de roll (sin comprar nada).
3. Escribir el pre-registro AMT (hipótesis, niveles, costos CFD, criterios IC90 inferior > 1.0) **antes** de construir `motor_amt.py`.
