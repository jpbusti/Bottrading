# Configuración del proyecto — 2026-10-08

Qué se dejó configurado, qué verifiqué y qué tienes que hacer tú. Todo lo dicho aquí se comprobó ejecutándolo en tu PC.

## 1. Hecho

| # | Qué | Estado |
|---|---|---|
| 1 | Paquetes instalados: statsmodels 0.15.0, quantstats 0.0.86, arch 8.0.0 (vectorbt/backtrader NO, a propósito) | ✅ `import statsmodels, quantstats, arch` sin errores |
| 2 | `requirements.txt` actualizado y `requirements.lock.txt` con versiones congeladas | ✅ probado en un entorno virtual NUEVO: instala y pasa `pytest` (29 tests) |
| 3 | Módulo común `validacion/` (7 archivos): `pf_inference`, `walkforward`, `placebo`, `cost_model`, `atr_grid`, `event_study`, `__init__` | ✅ creado y cubierto por tests (excepto `event_study`, ver abajo) |
| 4 | Funciones duplicadas extraídas: `pf`, `boot_pf`, `maxdd`, `mc_dd`, `walk_forward`, `costo_pts` (LSR) y `pf`, `resumen` (bootstrap), `monte_carlo_dd` (G2) ahora viven en `validacion/`; los motores las importan | ✅ numéricamente idéntico: el módulo reproduce el log de LSR v1 a 3 decimales |
| 5 | Restaurar `claude/PREREGISTRO_LSR_V1.md` y `RESULTADO_LSR_V1.md` | ❌ **imposible**: nunca estuvieron en git (único .md en todo el historial: `trade/README.md`) ni los encontré en el disco |
| 6 | Tests: control negativo LSR v1, señal aleatoria, bootstrap por bloques/día, costos | ✅ `tests/test_validacion.py` |
| 7 | Pre-registro de la siguiente hipótesis | ⏸ **No hecho a propósito**: tu mensaje pide primero proponer 3-5 hipótesis y esperar OK, y a la vez dice "no propongas hipótesis todavía". Prevaleció la regla explícita. Queda para la siguiente fase |
| 8 | Instalación limpia | ✅ ver punto 2 |
| 9 | Push desde esta sesión | ❌ requiere login interactivo (ver sección 3, paso 1) |
| + | Reporte de calidad NQ 2021-10 → 2026-10 | ✅ `data/raw/calidad/reporte_calidad_NQ_2021_2026.txt` (generado con `scripts/calidad_datos.py`) |
| + | `scripts/lsr/run_placebos.py`: placebo de nivel, dirección y timing para LSR | ✅ resultado en `resultados/lsr/placebos_NQ.txt` |
| + | Hooks de placebo en `motor_lsr.generar`: `invertir=True` y `timing_rng=` | ✅ |

## 2. Resultados del control negativo (LSR v1, NQ bloque A, combo central k=1.0 / m=1.75)

**Ojo: los números reales NO coinciden con los que citaste (PF 1.06 / IC90 inferior 0.84).** Los del log del proyecto (`resultados/lsr/resultado_lsr.log`) son estos, y el módulo nuevo los reproduce exactamente:

| Medida | Valor real (log y módulo) |
|---|---|
| Trades | 1,122 |
| PF neto | **0.998** |
| IC90 inferior / superior (iid) | **0.874** / 1.139 |
| Walk-forward OOS (8 folds, 2019-2026) | PF 1.016, IC90 inferior **0.877**, 901 trades |
| Folds con PF < 1.0 | 4 de 8 (2019, 2022, 2024, 2026) |
| Rejilla k×m | 0 de 9 puntos con PF ≥ 1.15; PF entre 0.991 y 1.004 |
| Placebo nivel D-2 (reproducido con datos regenerados) | PF 1.085, n=795 → **mejor que la estrategia real** |
| Placebo nivel D-3 / D-5 | 0.786 / 1.015 |
| Placebo dirección invertida | PF 0.931 |
| Placebo timing aleatorio (50 sorteos) | mediana 0.858, p95 0.931; p = 0.020 |

Veredicto del módulo: **RECHAZADA** (supera 0 de 3 placebos exigiendo además PF real > 1.0). El rechazo se mantiene. Lo que sí es cierto en todas las versiones: IC90 inferior < 1.0 y el placebo D-2 iguala/supera a la estrategia.

`[VERIFICAR]` De dónde salen 1.06 / 0.84: no coinciden con NQ ni con ES (0.898 / 0.781) del log. Pueden venir de una versión anterior de LSR o de la skill. Los tests usan los números del log, que sí pude reproducir.

Test de señal aleatoria (sintético, sin edge, costo 0.05R): PF bruto 1.007, PF neto 0.932, IC90 inferior 0.916 (< 1.0).

Test de bootstrap: con trades independientes, bloques e iid coinciden (±0.06); con rachas de signo constante, el bootstrap por bloques da un IC > 1.5× más ancho que el iid (el iid subestima la incertidumbre).

## 3. Lo que tienes que hacer tú

**Paso 1 — Login para que el push funcione**
- Qué: guardar tu credencial de GitHub una vez.
- Cómo: abre GitHub Desktop → File → Options → Accounts → Sign in. Luego, en tu terminal:
  ```powershell
  cd C:\Users\RYZEN\Desktop\MT\Bottrading
  git push -u origin main
  ```
  Si abre una ventana del navegador, autoriza.
- Verificar: `git status -sb` debe mostrar `## main...origin/main` sin `[ahead N]`.

**Paso 2 — `DATABENTO_API_KEY` (solo si vas a descargar datos nuevos; hoy NO hace falta)**
- Cómo: crea la clave en https://databento.com/portal → API Keys. Luego en PowerShell:
  ```powershell
  setx DATABENTO_API_KEY "db-tu_clave"
  ```
  Cierra y abre la terminal.
- Verificar: `python -c "import os; print('OK' if os.environ.get('DATABENTO_API_KEY') else 'FALTA')"` (no imprime la clave).

**Paso 3 — Costos reales del broker (esto sí bloquea un backtest serio)**
Hoy están todos los tramos con `verificado=False` en `validacion/cost_model.py`. Pídele a tu broker (o mira tu extracto):
1. Comisión + tarifas de bolsa/NFA **ida y vuelta por contrato** en NQ y en ES (hoy supuesto: $4.50 en ambos).
2. Spread típico en RTH por año (hoy supuesto: NQ 0.50 pts hasta 2019, 0.75 en 2020, 0.375 desde 2021; ES 0.25 / 0.375 / 0.25).
3. Slippage que has visto en órdenes de mercado (hoy: 1 tick por lado = 0.50 pts ida y vuelta).
Dónde ponerlos: edita la `TABLA` en `validacion/cost_model.py` (una línea por tramo), cambia `verificado=True` y escribe la `fuente`. Verificar: `python -c "from validacion import estado_verificacion as e; print(e())"` debe decir `sin_verificar: []`.

**Paso 4 — Calidad NQ 2021-2026: ya hecha**
Resultado: sin duplicados, sin huecos > 5 min, sin velas OHLC incoherentes, 45 sesiones con < 350 velas (medias sesiones de festivos). Revisa el archivo y confirma que te parece razonable. Para repetirlo: `python scripts\calidad_datos.py data\raw\NQ_databento_1m_10y_RTH.csv.gz salida.txt 2021-10-11 2026-10-06`.

**Paso 5 — Qué borrar del repo (tú decides; recomendación)**

| Archivo | Recomendación | Motivo |
|---|---|---|
| `scripts/pdh_pdl_lab.py` | **CONSERVAR** | lo importan `main.py`, `src/datos.py`, `src/motor/motor_estrategias.py` y `src/estrategias/pdh_pdl.py`; borrarlo rompe `main.py` y los tests de estrategias |
| `scripts/pdh_pdl_mt5_explorer.py` | **Borrar** | nadie lo importa (solo se menciona en un comentario del lab) |
| `data/raw/NQ_1d.csv`, `NQ_1h.csv` | **Conservar mientras uses `main.py`** | los lee `main.py`/el lab; los puedes volver a bajar con yfinance (`.gitignore` ya los excluye del repo) |
| `resultados/archivo/` (≈5 MB) | **Conservar** (es historia y evidencia del PF 1.63 in-sample) | pesa poco |
Comando para borrar solo lo recomendado (queda en el historial git para recuperarlo):
```powershell
cd C:\Users\RYZEN\Desktop\MT\Bottrading
git rm trade/scripts/pdh_pdl_mt5_explorer.py
git commit -m "Eliminar explorer PDH/PDL sin usos"
```

**Paso 6 — `gh` (GitHub CLI) o GitHub Desktop**
Recomendación: quédate con GitHub Desktop + el Git Credential Manager (ya configurado). `gh` solo aporta si quieres crear PRs desde la terminal; no es necesario. Si lo quieres: `winget install GitHub.cli` y `gh auth login`.

## 4. Pendiente / limitaciones honestas
- `event_study.py` está escrito pero **sin tests ni uso real**: se probará con su primera hipótesis.
- `placebo_timing` sortea la hora entre las velas 5m de la ventana permitida (no con el mismo bloque de volatilidad); es una definición razonable, no la única.
- Los pickles (`data/processed/lsr/*.pkl`) se regeneraron con los scripts existentes (NQ: 2,476 días, igual que el log). Están en `.gitignore`.
- Los motores `motor_lsr.py` y `motor_g2.py` siguen separados; solo se unificó la estadística. G2 no se re-ejecutó (faltan sus pkl `*_contratos_rth.pkl`; se regeneran con `scripts/g2/extraer_contratos.py`).
- No se corrió ningún backtest nuevo.
