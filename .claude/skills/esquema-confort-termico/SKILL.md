---
name: esquema-confort-termico
description: Contexto y procedimiento para armar el CSV único de confort térmico (ASHRAE 55), energía y carbono por escenario de la vivienda PUE-01 para el dashboard, solo con datos de los archivos dados.
---

# Esquema de datos de confort térmico — CSV único para el dashboard

Usa esta skill cuando se trabaje el esquema de datos del dashboard de confort térmico (proyecto de becario, vivienda mock **PUE-01**, proyecto SECIHTI de descarbonización en Puebla), o cuando se pida generar o corregir el CSV a partir de archivos (Revit/IFC, gbXML, índice de viviendas, salidas del simulador, EPW).

## 1. Qué se busca

- **Estándar fijo:** el confort siempre se mide con **ASHRAE 55** (adaptativo); no hay otro criterio ni opción de configuración.
- **Usuario final:** una persona de arquitectura que compara los tradeoffs de confort (y energía/carbono) de cambios a la vivienda. El CSV debe ser claro para ella: nombres legibles, un escenario = un conjunto de medidas, deltas contra el base ya calculados.
- Una vivienda de trabajo (PUE-01; PUE-01 y PUE-02 tienen datos mock), cada una con superficie fija y analizada por separado. Lo que cambia entre corridas son **medidas** sobre la envolvente u operación (valor U de muros/techo/ventanas, SHGC, absortancia, ventilación, velocidad del aire).
- Cada escenario se simula y se compara contra el caso base en **confort térmico (ASHRAE 55)**, **energía** y **carbono**.
- Todo vive en **un solo CSV** que el dashboard lee sin hacer uniones entre tablas.
- Interesan sobre todo el **mes caliente**, el **mes frío** y el **año**. No hay filas diarias.
- **La temperatura operativa la da un simulador preciso** (alimentado con los parámetros de `escenarios.csv`), **un valor por mes** y uno anual. El script no la calcula ni la reduce a máximos/mínimos. **Solo la temperatura exterior lleva máximo y mínimo.**

## 2. Regla principal: no inventar

Cada valor del CSV debe poder rastrearse a una de estas fuentes:
1. Un archivo dado (IFC/Revit, gbXML, índice, salida del simulador, EPW).
2. Algo que el usuario dijo explícitamente en la conversación (por ejemplo, factor de emisión o COP).
3. Constantes de ASHRAE 55 (fórmula adaptativa, bandas, límites de aplicabilidad), que son del estándar y no datos de la vivienda.

**No se permite:**
- Usar valores típicos de memoria (U de un block, factor de emisión de la red, COP de un equipo, horarios de ocupación).
- Convertir un rango estimado ("U ≈ 2–3") en un número.
- Rellenar huecos interpolando o copiando de otra vivienda.

**Si falta un dato:** la celda queda **vacía** (nunca "ND" en columnas numéricas) y se anota en el log `<salida>_log.md`, en *Datos faltantes*. Las decisiones de método (por ejemplo, usar la media exterior del mes como t_pma) van en *Supuestos de método*. Antes de entregar, se le dice al usuario qué quedó vacío y qué dato hace falta para llenarlo.

## 3. Estructura del CSV

**Una fila = escenario × periodo.** La vivienda se modela como **una sola zona, sin habitaciones** (v10 del esquema): no hay filas por cuarto ni fila TOTAL.

- Periodos (columna `periodo`): `anual`, `mes_caliente`, `mes_frio` y `ene` … `dic`.
  - El mes caliente y el mes frío salen **del clima**: el mes con la media exterior más alta y la más baja. `mes` dice cuál fue. `anual`, `mes_caliente` y `mes_frio` repiten datos de los meses: **no se suman** con ellos.
- **No se cuentan horas.** Por periodo: la T_op del simulador, el rango ASHRAE 55 del mes y cuánto se sale la T_op de él. No hay horas de confort, % de confort, grados-hora, ocupación ni desglose de energía. Solo la T exterior va con máximo y mínimo (y su media, que es la t_pma del mes).
- Cada fila trae el **estado completo** de la casa en ese escenario (todos los parámetros, no solo lo que cambió) y los supuestos, para que se pueda leer sola.

Formato: UTF-8, separador coma, punto decimal, encabezados en snake_case sin acentos y con la unidad en el nombre, 2 decimales. 27 columnas.

### Diccionario de columnas

| Columna | Unidad | Regla / fuente |
|---|---|---|
| vivienda_id | — | config (p. ej. PUE-01) |
| escenario_id, escenario_nombre | — | tabla de escenarios (ESC-00 = base) |
| es_base | Si/No | exactamente un escenario Si |
| U_muro_ext, U_techo, U_ventana | W/m²K | valor U del elemento completo, de archivo o del usuario (nunca los valores por defecto de Revit del IFC/gbXML) |
| SHGC_ventana | 0–1 | ídem |
| absortancia_muro, absortancia_techo | 0–1 | ídem |
| ventilacion_ach | 1/h | renovaciones de aire |
| vel_aire_m_s | m/s | velocidad del aire interior supuesta en el escenario |
| periodo | — | anual, mes_caliente, mes_frio, ene…dic |
| mes | 1–12 | vacío en anual |
| T_ext_max_C, T_ext_min_C | °C | máximo y mínimo exterior del periodo (EPW o `clima.csv`) |
| T_ext_media_C | °C | media exterior del periodo; en un mes es la t_pma de ASHRAE 55 |
| T_operativa_C | °C | del simulador, punto central de la vivienda, tal cual (fila del mes o `anual`); vacía en `anual` si el simulador no la da |
| limite_sup_C | °C | límite superior ASHRAE 55 del mes: 0.31·t_pma + 17.8 + banda (3.5 u 2.5), más el ajuste por velocidad del aire; vacío en `anual` |
| limite_inf_C | °C | límite inferior ASHRAE 55 del mes; vacío en `anual` |
| exceso_sobre_limite_C | °C | máx(0, T_op − límite superior); en `anual`, el del peor mes |
| deficit_bajo_limite_C | °C | máx(0, límite inferior − T_op); en `anual`, el del peor mes |
| energia_total_kWh | kWh | enfriamiento + calefacción del simulador (cargas ideales); año = suma de meses; se convierte a eléctrica solo con COP/eficiencia dados |
| carbono_kgCO2e | kgCO₂e | energia_total_kWh × factor_emision_kgCO2e_kWh (solo si el factor fue dado) |
| delta_fuera_rango_C | °C | (exceso + déficit) del escenario − (exceso + déficit) del base, mismo periodo; negativo = mejora |
| delta_energia_pct | % | ídem; vacío si la base es 0. El delta de carbono sería igual (mismo factor), por eso no existe |
| aceptabilidad_pct | % | config (80 o 90) |

## 4. Lógica de cálculo (ASHRAE 55, método adaptativo)

Detalle completo, con ejemplo numérico y limitaciones: `metodologia_calculo.md` (en el repositorio: `docs/metodologia_calculo.md`). Las fórmulas están verificadas contra pythermalcomfort con `backend/pruebas/validar_ashrae55.py`.


- **Punto de medición:** el simulador entrega la temperatura operativa de **un punto central de la vivienda**, lejos de los muros, como `T_operativa_C` por mes. El script no la calcula (no hay aire + radiante).
- **t_pma** = media exterior del mes (ventana de ~30 días, el tope de ASHRAE 55), porque la T_op es mensual.
- **T_confort** = 0.31·t_pma + 17.8. Banda de ±3.5 °C (80 %) o ±2.5 °C (90 %).
- **Aplicabilidad:** 10 ≤ t_pma ≤ 33.5 °C. Un mes fuera de ese rango queda sin límites ni exceso/déficit y se avisa en el log.
- **Velocidad del aire** (`vel_aire_m_s` del escenario; cuando T_op > 25 °C, solo el límite superior): +1.2 °C (0.6 m/s), +1.8 °C (0.9 m/s), +2.2 °C (1.2 m/s).
- **Año:** T_op de la fila `anual` del simulador; sin límites propios; exceso/déficit = el del peor mes; energía = suma de los 12 meses.

## 5. Procedimiento

1. **Inventario.** Lista los archivos dados y qué columna del esquema puede salir de cada uno:
   - `PUE-01_Diana.ifc`: geometría para el simulador. Sus U, absortancias y materiales son por defecto de Revit (ventanas U 3.69, una losa U 80, muros de "Yeso" sin capas, todos marcados exteriores): no se usan como parámetros (ver pendiente 8 del contexto).
   - `Indice_viviendas_Puebla_SECIHTI.xlsx`, hoja `IFC_espacios`: ya no aporta columnas al CSV (el área total no se reporta).
   - `gbXML_PUE-01_analisis.xlsx`: volúmenes y avisos de calidad. Los valores térmicos del gbXML son **por defecto de Revit** (Madrid, oficina, R-13…) y no se usan como parámetros de escenario.
   - Tabla de escenarios / medidas que dé el usuario: parámetros U, SHGC, etc.
   - Salidas del simulador (DesignBuilder/EnergyPlus): un valor por mes (y anual) de la vivienda completa (una sola zona; si el modelo tiene varios cuartos, se reduce a un valor antes del script, p. ej. un nodo térmico o promedio ponderado por área).
   - EPW de Puebla, o una tabla mensual de clima: T exterior máx, mín y media por mes.
2. **Arma las entradas del script** en una carpeta de trabajo:
   - `escenarios.csv`: escenario_id, escenario_nombre, es_base, archivo_resultados + los 8 parámetros (vacíos si no están en los archivos).
   - `config.csv` (clave,valor): vivienda_id, aceptabilidad_pct, factor_emision_kgCO2e_kWh, energia_tipo (electrica/termica), COP_enfriamiento, eficiencia_calefaccion. Solo lo dado.
   - `clima.csv` (si no hay EPW): mes, T_ext_max_C, T_ext_min_C, T_ext_media_C.
   - Un `resultados_<escenario>.csv` por escenario con columnas normalizadas: mes (1–12, y `anual` si se tiene), T_operativa_C, energia_enfriamiento_kWh, energia_calefaccion_kWh. Para EnergyPlus/DesignBuilder: la operativa mensual del punto central → T_operativa_C, "Zone Ideal Loads … Cooling/Heating Energy [J]" mensual ÷ 3.6e6 → kWh (energia_tipo = termica). Solo cambios de nombre y de unidad, nada más; el valor mensual se copia tal cual.
3. **Ejecuta** el script de la sección 7:
   `python3 generar_csv_confort.py --escenarios escenarios.csv --config config.csv (--epw clima.epw | --clima clima.csv) --salida confort_PUE-01.csv`
   Dentro del repositorio del proyecto: `python backend/generar_csv_confort.py … --salida datos/confort_<vivienda>.csv`. Todo CSV que quede en `datos/` lo lee el dashboard automáticamente.
4. **Valida** antes de entregar:
   - Filas = escenarios con resultados × 15.
   - Un solo `es_base = Si`, y sus deltas son 0.
   - Para cada escenario y periodo: T_ext_min_C ≤ T_ext_media_C ≤ T_ext_max_C; limite_inf_C < limite_sup_C; exceso y déficit ≥ 0 y nunca ambos > 0 en un mes; mes_caliente y mes_frio idénticos a su mes; T_operativa_C idéntica a la del archivo del simulador.
   - Los resultados no tienen `mes` repetido (un solo valor por mes y escenario).
   - `mes` lleno en mes_caliente/mes_frio.
   - Abre el log y revisa cada faltante: ¿de verdad no estaba en ningún archivo?
5. **Entrega** el CSV y el log, y di en 2–3 líneas qué quedó vacío y qué dato lo llenaría.

## 6. Contexto de PUE-01 (de los archivos)

- Casa Luis Bautista, San Bernardino Tlaxcalancingo (San Andrés Cholula), 2 niveles. Modelo Revit de Diana Aguilar (`PUE-01_Diana.ifc`).
- 13 espacios acondicionados, tratados como una sola zona: 185.4 m², 421.6 m³. Cochera y patio no están acondicionados.
- Norte real −20.5°. Medianeras E, S, O (adiabáticas). Muro expuesto ~96 m², ventanas exteriores 9.66 m², WWR global ≈ 0.10.
- Los valores de construcción "reales" del análisis del gbXML son **estimados a confirmar en campo** (rangos): no se usan como números sin confirmación del usuario.

## 7. Script de referencia

`scripts/generar_csv_confort.py` (necesita pandas y numpy; copia de `backend/generar_csv_confort.py` del repositorio, que es la fuente de verdad). Úsalo tal cual: no copies su código aquí. Tras cambiar el backend o el contexto, corre `python herramientas/empaquetar_skill.py` para sincronizar la skill y generar `dist/esquema-confort-termico.skill`. Se probó con el mock de `backend/mock/crear_mock.py` (5 escenarios, `clima.csv` mensual, sin EPW).

## 8. Mejora continua

Si un cambio al esquema se acuerda con el usuario: actualiza `COLUMNAS` y el diccionario, sube la versión (v10 → v11) en el docstring y registra el cambio en el MD de contexto del proyecto (`docs/contexto_esquema_confort.md`), en la sección de historial, y vuelve a empaquetar la skill.
