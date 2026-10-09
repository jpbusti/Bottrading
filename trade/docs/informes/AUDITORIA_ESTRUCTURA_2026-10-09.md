# Auditoria de estructura (2026-10-09)

## 1-2. Estrategias y cumplimiento del estandar (`docs/ESTANDAR_ESTRATEGIA.md`)
| Estrategia | Carpeta | Estado | Antes | Ahora |
|---|---|---|---|---|
| LSR v1 | `scripts/lsr/` | rechazada | motor + run_lsr + run_placebos + 2 utilidades de datos; sin config ni README | + `config.yaml` (vigilado por test), `README.md`, `__init__.py`. Motor intacto |
| G2 | `scripts/g2/` | no aprobada | motor + run_validacion + control_test + extraer_contratos | + `config.yaml`, `README.md`, `__init__.py`. Motor intacto |
| US100 v1 | `scripts/us100/` -> `scripts/us100_v1/` | ninguna aprobada | motor + run, constantes en codigo | renombrada; + `config.yaml`, `README.md`; resultados en `resultados/us100_v1/` |
| US100 ORB | `scripts/us100_orb/` | pre-registro pendiente de firma | no existia | estructura completa del estandar + `tests/test_us100_orb.py` |
Las tres legado cumplen el estandar solo parcialmente (decision: no partir motores cuya reproduccion esta verificada). Detalle en el estandar.

## 3. Archivos sueltos
- `scripts/calidad_datos.py`, `scripts/descarga/*`: utilidades de datos, no estrategias. Se quedan en `scripts/`.
- `scripts/g2/extraer_contratos.py`, `scripts/lsr/extraer_contratos_ext.py`, `scripts/lsr/unir_nq.py`: preparacion de datos de NQ/ES; sin mover (los usan los README de G2/LSR).
- Movido a `scripts/_archivo/`: `marco_subastas/`, documentos desactualizados y datos locales obsoletos (ignorados).

## 4. Parametros hardcodeados que NO se extrajeron (legado) [VERIFICAR al migrar]
- LSR: ventanas horarias de bloques A/B, umbral volumen 1.5x/20 velas, lista FOMC (`motor_lsr.py`), lags de placebos y combo central (`run_lsr.py`).
- G2: costos y fechas por instrumento (`run_validacion.py`), `METODOS_DECISION`.
- US100 v1: umbrales por hipotesis en `senal()` (0.10/0.60/0.15/0.50/0.20), rejilla y `N_TIMING` en `run_us100.py` (estos ultimos si estan en su `config.yaml` como referencia).
Los `config.yaml` de las legado contienen las constantes de modulo, comprobadas por `tests/test_config_legado.py`.

## 5. Tests
`tests/` = 71 pasan + 3 xfail (el xfail es un requisito de costo ES >= 1.10 pts que el dato dictado no cumple; documentado en el propio test).
| Archivo | Cubre |
|---|---|
| `test_validacion.py` | motor `validacion/` + control negativo LSR v1 contra su log |
| `test_cost_model_cfd.py` | `validacion/cost_model.py` (CFD) |
| `test_us100_v1.py` | motor US100 v1 |
| `test_us100_orb.py` | estrategia nueva + regla validacion no importa scripts |
| `test_config_legado.py` | anti-deriva de los config.yaml legado |
Se eliminaron antes, junto con el motor viejo NQ/ES, `test_estrategias.py`, `test_indicadores.py` y `conftest.py`.

## 6. Pre-registros y resultados (todos en `docs/`)
PREREGISTRO: `G2_VALIDACION`, `LSR_V1`, `US100_V1`, `US100_ORB` (pendiente de firma). RESULTADO: `G2_VALIDACION`, `LSR_V1`, `US100_V1`.
Informes: `docs/informes/` (auditorias, configuracion). Planes: `docs/planes/`. Salidas numericas: `resultados/{lsr,g2,us100_v1,us100_orb}/`.
