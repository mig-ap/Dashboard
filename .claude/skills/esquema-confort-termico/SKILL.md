---
name: esquema-confort-termico
description: Importa información de archivos de proyecto (IFC/Revit, gbXML, planos, fichas técnicas) y de bases de datos públicas (clima por ubicación y periodo) para armar, sin inventar datos, el esquema de confort térmico ASHRAE 55 (CSV del dashboard, v10, 27 columnas) de una vivienda. Úsala al recibir un IFC o modelo de Revit, al pedir el clima de un lugar, al llenar escenarios, config o trazabilidad, o al generar o validar el CSV de confort.
---

# Esquema de confort térmico — importación sin inventar datos

Usa esta skill para convertir lo que dé la persona usuaria (IFC exportado de Revit, gbXML, planos, fichas técnicas, resultados del simulador) en el **CSV único del dashboard de confort térmico** (ASHRAE 55 adaptativo, una vivienda = una zona). Funciona con cualquier vivienda; PUE-01 (Puebla) es el caso de trabajo del proyecto SECIHTI.

Todo lo que necesitas está en esta carpeta:

| Archivo | Para qué |
|---|---|
| `scripts/extraer_ifc.py` | lee el IFC y separa lo útil de los valores por defecto de Revit |
| `scripts/clima_por_ubicacion.py` | temperatura exterior mensual de una base de datos pública, por ubicación y periodo |
| `scripts/calcular_u.py` | valor U por capas (ISO 6946), cada conductividad con su fuente |
| `scripts/armar_entradas.py` | pasa la trazabilidad confirmada a las entradas del esquema |
| `scripts/generar_csv_confort.py` | genera el CSV final (necesita resultados del simulador) |
| `plantillas/trazabilidad.csv` | lista de todos los datos que hay que conseguir, con su origen esperado |
| `metodologia_calculo.md`, `contexto_esquema_confort.md` | fórmulas ASHRAE 55 e historial de decisiones |

Los cuatro primeros scripts solo usan la biblioteca estándar de Python 3.10+. `generar_csv_confort.py` necesita `pandas` y `numpy` (`pip install pandas numpy`). `clima_por_ubicacion.py` necesita internet.

## 1. Regla principal: cada valor tiene un origen verificable

Ningún valor entra al esquema si no se puede rastrear a una de estas fuentes, en este orden de preferencia:

1. **Archivo del proyecto** (IFC, gbXML, planos), solo si el valor no es uno por defecto del programa. `extraer_ifc.py` lo detecta.
2. **Base de datos pública consultable**, con la URL o el documento y el año exactos. Por ejemplo, el clima por ubicación y periodo, o el factor de emisión oficial de la red.
3. **Ficha técnica del fabricante** o **tabla de una norma**, citando el documento, la tabla y la edición.
4. **Constantes de una norma** (ASHRAE 55, ISO 6946). Son del estándar, no datos de la vivienda.
5. **Algo que la persona usuaria dijo explícitamente** en la conversación.

**Prohibido:**
- Valores "típicos" de memoria (U de un block, SHGC de un vidrio, factor de emisión, COP).
- Convertir un rango ("U ≈ 2–3") en un número.
- Copiar datos de otra vivienda.
- Interpolar.
- Usar valores marcados "revisar" sin confirmación.
- **Generar datos con una simulación propia.**

La temperatura operativa y la energía **solo** salen del simulador del proyecto, cuando entregue sus resultados. Hasta entonces quedan como pendiente y el CSV final no se genera.

Si un dato no tiene fuente, queda **vacío** y va a `pendientes.md` junto con lo que haría falta para llenarlo.

## 2. Qué origen admite cada dato del esquema

| Dato | Origen admitido | Cómo se obtiene |
|---|---|---|
| Ubicación (lat, lon) | IFC (si no es por defecto), dirección o municipio de los documentos, persona usuaria | `extraer_ifc.py`; si es por defecto, `clima_por_ubicacion.py --lugar … --municipio …` |
| `T_ext_max_C`, `T_ext_min_C`, `T_ext_media_C` | base de datos climática pública | `clima_por_ubicacion.py` (ERA5-Land vía Open-Meteo; contraste opcional con NASA POWER) o un EPW de una base pública |
| `U_muro_ext`, `U_techo` | ficha técnica; cálculo por capas con espesores del IFC o planos y conductividades de norma o ficha | `calcular_u.py`; el U que trae el IFC solo con confirmación |
| `U_ventana`, `SHGC_ventana` | ficha técnica del vidrio o la ventana | el IFC de Revit suele traer valores genéricos: `extraer_ifc.py` los marca |
| `absortancia_muro`, `absortancia_techo` | ficha técnica del acabado, medición | ídem |
| `ventilacion_ach`, `vel_aire_m_s` | decisión de la persona usuaria (operación), prueba de hermeticidad | preguntar |
| `factor_emision_kgCO2e_kWh` | publicación oficial vigente del factor de emisión de la red eléctrica (en México, el factor del Sistema Eléctrico Nacional que publica la autoridad) | buscar la edición más reciente y citar documento y año; si no se puede verificar, vacío |
| `aceptabilidad_pct`, `energia_tipo`, escenarios (`escenario_nombre`, medidas) | persona usuaria | preguntar |
| `COP_enfriamiento`, `eficiencia_calefaccion` | ficha técnica del equipo | solo si `energia_tipo = termica` |
| `T_operativa_C`, energía de enfriamiento y calefacción | **simulador del proyecto** | archivo con el formato de `resultados_PLANTILLA.csv` |
| Límites, exceso/déficit, deltas, carbono, periodos | calculados por `generar_csv_confort.py` | — |

## 3. Procedimiento

Trabaja en una carpeta nueva (p. ej. `trabajo_<vivienda>/`). `S` es la carpeta `scripts/` de esta skill.

1. **Inventario y preguntas.** Lista los archivos recibidos y pregunta, sin suponer:
   - la ubicación real, si no viene clara;
   - el **periodo climático**: años completos, p. ej. los últimos 10;
   - los escenarios (qué medidas cambian contra el base);
   - la aceptabilidad (80 o 90 %) y cómo entregará la energía el simulador.
2. **IFC:** `python S/extraer_ifc.py modelo.ifc --salida trabajo/`. Lee `ifc_hallazgos.md` y explícale a la persona qué sirve (geometría para el simulador) y qué no (ubicación o valores térmicos por defecto, con sus motivos).
3. **Ubicación y clima:**
   `python S/clima_por_ubicacion.py --lugar "<localidad>" --municipio "<municipio>" --desde AAAA --hasta AAAA --verificar-nasa --salida trabajo/`
   - Si el script lista varios candidatos, **pregunta cuál es**; no escojas tú.
   - Si no hay internet, entrega la URL que imprime para que la persona descargue el JSON.
   - Con un EPW de una base pública (p. ej. climate.onebuilding.org), úsalo directo en el paso 6 con `--epw`.
4. **Parámetros de los escenarios:** llena `trazabilidad.csv` (copia de `plantillas/trazabilidad.csv`). En cada fila van `valor`, `origen`, `fuente` (documento, tabla, URL, página) y `estado`:
   - **`confirmado`**: solo cuando la fuente es verificable o la persona lo confirmó;
   - **`revisar`**: candidatos aún sin confirmar;
   - **`faltante`**: sin dato.
   Usa `=base` cuando una medida no cambia en un escenario y la persona lo confirmó. Para un U por capas: `python S/calcular_u.py capas.csv --elemento muro|techo`, y agrega su fila a la trazabilidad.
5. **Armar entradas:** `python S/armar_entradas.py trazabilidad.csv trabajo/trazabilidad_ifc.csv trabajo/trazabilidad_clima.csv --salida trabajo/entradas/`. Escribe `escenarios.csv`, `config.csv`, `resultados_PLANTILLA.csv` y `pendientes.md`. Copia `clima.csv` a `entradas/`.
6. **Resultados del simulador:** entrega `resultados_PLANTILLA.csv` a quien simula; un archivo `resultados_<ESC>.csv` por escenario. Cuando estén, ejecuta:
   `python S/generar_csv_confort.py --escenarios entradas/escenarios.csv --config entradas/config.csv --clima entradas/clima.csv --salida confort_<vivienda>.csv`
7. **Valida y entrega:**
   - filas = escenarios × 15;
   - un solo base, con deltas en 0;
   - en cada mes, `limite_inf_C < limite_sup_C` y nunca exceso y déficit a la vez;
   - el log no tiene faltantes sin explicar.

   Entrega el CSV, su log, `trazabilidad.csv` y `pendientes.md`, y di en 2–3 líneas qué quedó vacío y qué dato lo llenaría.

## 4. Lo que suele traer un IFC de Revit (y no se usa sin confirmar)

- **Emplazamiento por defecto:** el sitio se llama "Default" o "Emplazamiento por defecto", la dirección dice "Introduzca dirección aquí", y las coordenadas son de otra ciudad. Revit trae Madrid (40.42, −3.71) si nadie lo cambió.
- **U y SHGC genéricos:** el mismo valor en tipos de ventana muy distintos. Por ejemplo, U 3.69 W/m²K ≈ 0.65 Btu/h·ft²·°F y SHGC 0.78.
- **Absortancia 0.7** en los tipos "Por defecto".
- **U imposibles:** por ejemplo, 80 W/m²K.
- **Muros sin capas:** un solo material genérico, así que el U no se puede calcular desde el IFC.
- **`IsExternal` en todos los muros:** incluye medianeras e interiores.
- **Áreas sin la cantidad IFC estándar:** `extraer_ifc.py` usa el área de Revit (`Dimensions.Area`) y dice cuántas.

La geometría (áreas, volúmenes, vanos) sí sirve, sobre todo para el simulador.

## 5. Estructura del CSV (v10, 27 columnas)

**Una fila = escenario × periodo.** Periodos: `anual`, `mes_caliente`, `mes_frio` y `ene` … `dic` (15 por escenario). El mes caliente y el frío salen del clima: el de media exterior más alta y más baja. Esas tres filas repiten datos de los meses: **no se suman** con ellos. La vivienda es una sola zona. Formato: UTF-8, coma, punto decimal, 2 decimales, celda vacía = sin dato.

| Columna | Unidad | Regla / fuente |
|---|---|---|
| vivienda_id | — | config |
| escenario_id, escenario_nombre | — | escenarios (ESC-00 = base) |
| es_base | Si/No | exactamente un escenario Si |
| U_muro_ext, U_techo, U_ventana | W/m²K | > 0; ficha técnica o cálculo por capas (nunca un valor por defecto de Revit) |
| SHGC_ventana | 0–1 | ficha técnica del vidrio |
| absortancia_muro, absortancia_techo | 0–1 | ficha técnica del acabado o medición |
| ventilacion_ach | 1/h | ≥ 0; supuesto de operación de la persona usuaria |
| vel_aire_m_s | m/s | ≥ 0; velocidad del aire interior (ventilador) |
| periodo, mes | — | anual, mes_caliente, mes_frio, ene…dic; mes 1–12 (vacío en anual) |
| T_ext_max_C, T_ext_min_C, T_ext_media_C | °C | base de datos climática; la media del mes es la t_pma de ASHRAE 55 |
| T_operativa_C | °C | **simulador**, punto central, tal cual; vacía en `anual` si no la da |
| limite_sup_C, limite_inf_C | °C | 0.31·t_pma + 17.8 ± banda (3.5 u 2.5), más el ajuste por ventilador; vacíos en `anual` |
| exceso_sobre_limite_C, deficit_bajo_limite_C | °C | máx(0, T_op − sup) y máx(0, inf − T_op); en `anual`, el peor mes |
| energia_total_kWh | kWh | **simulador**; año = suma de meses; a eléctrica solo con COP/eficiencia dados |
| carbono_kgCO2e | kgCO₂e | energía × factor de emisión citado |
| delta_fuera_rango_C | °C | (exceso + déficit) del escenario − del base; negativo = mejora |
| delta_energia_pct | % | contra el base; vacío si la base es 0 |
| aceptabilidad_pct | % | config (80 o 90) |

Humedad, sombreado y grados-hora **no** forman parte del esquema (v10): no entran en ASHRAE 55 adaptativo ni cambian la lectura. No los agregues sin que la persona usuaria lo pida.

## 6. ASHRAE 55 adaptativo (resumen)

- **t_pma:** media exterior del mes.
- **T_confort** = 0.31·t_pma + 17.8, con banda de ±3.5 °C (80 %) o ±2.5 °C (90 %).
- **Rango válido:** solo con 10 ≤ t_pma ≤ 33.5 °C.
- **Ventilador:** si T_op > 25 °C, el límite superior sube +1.2, +1.8 o +2.2 °C con 0.6, 0.9 o 1.2 m/s.
- **Año:** sin rango propio; su exceso/déficit es el del peor mes.

Detalle y ejemplo numérico en `metodologia_calculo.md`.

## 7. Mantenimiento

Copia de un repositorio. Las fuentes de verdad son:
- `backend/generar_csv_confort.py`
- `backend/importacion/*.py`
- `docs/`

Tras cambiarlas, `python herramientas/empaquetar_skill.py` resincroniza esta carpeta y genera `dist/esquema-confort-termico.skill`, el archivo que se instala en Claude (Cowork o Code).

Un cambio de esquema se acuerda con la persona usuaria y se registra en el historial de `contexto_esquema_confort.md`.
