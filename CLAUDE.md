# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Thermal-comfort dashboard for an intern project inside the SECIHTI housing-decarbonization project (Puebla). Each dwelling (mock: PUE-01, PUE-02) is modeled as a **single thermal zone** whose operative temperature/humidity come from a central point of the house, produced by an external precise simulator fed with each scenario's parameters (one value per month + annual); scenarios vary envelope/operation measures. Question answered: which changes improve ASHRAE 55 comfort most, and at what energy/carbon cost, focusing on the hot month, cold month and year. Docs, code identifiers and UI text are in Spanish. `README.md` is the user-facing guide.

Layout:
- `backend/generar_csv_confort.py` — the whole pipeline (pandas/numpy, `backend/requirements.txt`). Source of truth.
- `backend/mock/crear_mock.py` — fake inputs into `backend/mock/entradas/<vivienda>/` (gitignored); it stands in for the simulator (monthly `resultados_<ESC>.csv` + `clima.csv`).
- `datos/` — output CSVs. The dashboard reads **every** `.csv` here (any number of dwellings); `_log.md` files are ignored by it.
- `dashboard/index.html` — static page (Chart.js + PapaParse from cdnjs). `dashboard/servidor.py` (stdlib only) serves it plus `/api/csv` (list of CSVs in `datos/`) and `/datos/<file>.csv`. Without the server the page only works via its multi-file picker.
- `docs/metodologia_calculo.md` — every formula (ASHRAE 55 adaptive), step by step, mapped to script functions, with assumptions/limitations. Update it whenever a calculation changes.
- `docs/contexto_esquema_confort.md` — decision history (v1–v10), column list, calculation logic, open questions. Read before changing the schema.
- `.claude/skills/esquema-confort-termico/` — project-local skill. Its `scripts/` and context copy are synced from `backend/` and `docs/` by `python herramientas/empaquetar_skill.py`, which also builds `dist/esquema-confort-termico.skill` (gitignored). Run it after editing either source.

## Commands

```
pip install -r backend/requirements.txt
python backend/mock/crear_mock.py --vivienda PUE-01 [--ajuste-clima 0]
python backend/generar_csv_confort.py --escenarios backend/mock/entradas/PUE-01/escenarios.csv --config backend/mock/entradas/PUE-01/config.csv (--clima backend/mock/entradas/PUE-01/clima.csv | --epw clima.epw) --salida datos/confort_PUE-01_mock.csv
python dashboard/servidor.py [--puerto 8000] [--datos datos] [--sin-navegador]
python herramientas/empaquetar_skill.py
pip install -r backend/requirements-dev.txt && python backend/pruebas/validar_ashrae55.py   # checks formulas vs pythermalcomfort
```
The ASHRAE 55 formulas are hand-written in the script on purpose; `pythermalcomfort` is a dev-only reference, never a runtime dependency. No linter exists. `archivo_resultados` in `escenarios.csv` is resolved relative to that file. Mock dwellings: PUE-01 `--ajuste-clima 0`, PUE-02 `--ajuste-clima 4`.

## Architecture / invariants

Flow: simulator results per scenario, one row per month (+ optional `anual`) with `T_operativa_C` and energy (any `HR_pct` is ignored) → monthly climate (`leer_clima`, EPW or `--clima`: T_ext max/min/mean) → prevailing mean = monthly outdoor mean → `limites` per month → exceedance/deficit = T_op − limit → annual row (simulator's annual T_op, no limits, worst-month exceedance/deficit, energy = sum of months) → deltas vs. the single `es_base` scenario (`delta_fuera_rango_C` = Δ of exceso + déficit, `delta_energia_pct`).

Output is one long-format CSV per run, one row = scenario × periodo (15 per scenario), 27 columns fixed by `COLUMNAS`. The `anual`, `mes_caliente` and `mes_frio` rows overlap the monthly rows and must never be summed with them. Only add a column if it enters a calculation or changes what the reader concludes (v10 removed `sombreado_m`, `HR_pct`, `nivel`, `delta_T_operativa_C`). Changing the schema means updating `COLUMNAS`, the skill's column dictionary, the context doc, and the dashboard (`REQUERIDAS` and the fields it reads). The dashboard merges all CSVs keyed by `vivienda_id × escenario_id × periodo` (later file alphabetically wins) and colors scenarios by their order in the data, never by filter position. Light theme only (white + navy). The tradeoff scatter identifies scenarios by direct text labels, not by color (5+ categorical colors fail the all-pairs check in a scatter). Layout must not overflow from 390 to 1920 px wide. The ASHRAE range depends only on the month's climate, so the dashboard shows it once per period (not per scenario) and only flags scenarios whose fan raises `limite_sup_C`; the CSV still carries the limits on every row.

Rules that must be preserved:
- Comfort is ALWAYS measured with ASHRAE 55 adaptive; it is not configurable. PMV/PPD may only be a complementary addition.
- The audience is someone from architecture comparing comfort tradeoffs: keep columns few, clearly named, with deltas vs. base precomputed.
- **Never invent data.** Missing input → empty cell + entry in the log (`log("faltantes"|"supuestos"|"avisos", ...)`). No "typical" U-values, emission factors, COPs; ranges are not turned into numbers.
- T_op comes from the simulator, one value per period, copied as given: the script never computes, averages or reduces it to max/min (a missing annual value stays empty). Only outdoor temperature is reported as max/min. No hour counts, % comfort, degree-hours or occupancy.
- Single zone: no `espacio_id`; reducing a multi-room model to one value happens before the script.
- Thermal energy is converted to electric only if `energia_tipo=termica` and COP/efficiency are given; carbon is operational only (energy × given factor), so only `delta_energia_pct` exists.
- Adaptive method is valid only for prevailing mean 10–33.5 °C; months outside get no limits or exceedance/deficit and are reported in the log.
- Each scenario row carries the full state of the house (all 8 parameters); the dashboard shows only those that differ from the base.
