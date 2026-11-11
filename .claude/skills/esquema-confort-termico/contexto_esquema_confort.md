## 1. Propósito

Este documento guarda todo el contexto del **esquema de datos del dashboard de confort térmico**: qué se busca, cómo se llegó al diseño actual, la lógica de cálculo y lo que falta decidir. Sirve para retomar el trabajo sin perder decisiones y para seguir mejorando el esquema pensando en el dashboard final.

- **Proyecto:** dashboard propio de confort térmico (proyecto de becario), dentro del proyecto SECIHTI de descarbonización de vivienda en Puebla.
- **Viviendas:** PUE-01 es la vivienda de trabajo; PUE-01 y PUE-02 tienen hoy solo datos mock. Cada vivienda tiene superficie fija y se analiza por separado; lo que cambia entre escenarios son las medidas. El esquema admite cualquier número de viviendas (`vivienda_id`).
- **Pregunta que responde el dashboard:** ¿qué cambios a la vivienda mejoran más el confort térmico, y cuánto cuestan en energía y carbono? Lo que más interesa son los casos límite (mes caliente y mes frío).
- **Estándar fijo:** el confort siempre se mide con **ASHRAE 55** (método adaptativo). No es configurable: el script no tiene ninguna opción para cambiar de método.
- **Usuario final:** una persona de arquitectura que usa el CSV/dashboard para comparar los tradeoffs que producen los cambios a la vivienda en el confort. Por eso el esquema debe poder leerse sin conocimientos de simulación: pocas columnas con nombres claros, un escenario = un conjunto de medidas arquitectónicas, y la comparación contra el base ya calculada (`delta_*`).
- **Objetivo de la simulación:** obtener la temperatura operativa del inmueble, medida en **un punto central de la vivienda** para idealizar la temperatura y reducir la varianza cerca de las paredes. Desde v9 la temperatura operativa la entrega **un simulador preciso** alimentado con los parámetros de cada escenario, como **un valor por mes** (y uno anual) en `resultados_<escenario>.csv`; el script no la calcula ni la reduce a máximos/mínimos.
- **Modelo (desde v7):** la vivienda se trata como **una sola zona, sin habitaciones**. Las condiciones de todos los cuartos se generalizan en un solo valor por periodo; no hay datos ni filas por cuarto.
- **Herramienta asociada:** skill `esquema-confort-termico`, que contiene el esquema, las reglas y el script `generar_csv_confort.py` para armar el CSV desde los archivos dados, sin inventar datos.
- **Repositorio:** `backend/` genera los CSV, `datos/` los guarda (el dashboard lee todos los `.csv` de esa carpeta, de cualquier número de viviendas), `dashboard/` los muestra, `docs/` tiene este contexto y `.claude/skills/` la skill.

## 2. Archivos de origen disponibles

Todos estaban en el zip "Re: Hola":

| Archivo | Qué aporta | Uso en el esquema |
|---|---|---|
| `PUE-01_Diana.ifc` | Modelo 3D exportado de Revit (IFC4) | Geometría para el simulador (áreas, volúmenes, vanos). Sus propiedades térmicas son **por defecto de Revit** (no usar); ver pendiente 8 |
| `Indice_viviendas_Puebla_SECIHTI.xlsx` | Índice de 8 viviendas + hojas IFC_* + WWR | `IFC_espacios`: área total de la vivienda (suma de espacios acondicionados) |
| `aguilarcoleote…ProyectoCasaNaranja-1.xml` | gbXML de Revit | Geometría y volúmenes; datos térmicos **por defecto de Revit** (no usar) |
| `gbXML_PUE-01_analisis.xlsx` | Análisis del gbXML contra la realidad | Volumen 421.6 m³; checklist de exportación; valores reales estimados (rangos) |
| `…FACHADASCORTESARQ_FINALES_CASALUISB.pdf` | Planos de fachadas y cortes | Referencia visual |
| `PUE-01_diagrama.png` | Plantas con condición de frontera de cada muro | Referencia: exterior / no acondicionado / medianera |

**Lo que no hay todavía:** simulación energética, archivo EPW de Puebla y la tabla de escenarios con valores confirmados.

**Datos de PUE-01 (de los archivos):**
- Casa Luis Bautista, Tlaxcalancingo, 2 niveles.
- 13 espacios acondicionados: 185.4 m², 421.6 m³.
- Norte real −20.5°. Medianeras E, S, O.
- Muro expuesto ~96 m², ventanas exteriores 9.66 m², WWR ≈ 0.10.

**Valores base estimados (por confirmar en campo):**
- Block 15 cm, U ≈ 2–3 W/m²K
- Losa de concreto, U ≈ 3 W/m²K
- Vidrio sencillo, U ≈ 5.8 W/m²K

## 3. Cómo evolucionó el esquema (historial de decisiones)

| Versión | Qué se propuso | Qué se corrigió y por qué |
|---|---|---|
| v1 | Excel de 10 hojas (viviendas, zonas, materiales, simulaciones, resultados horarios, confort) | Era genérico, para varias viviendas |
| v2 | Una vivienda; columnas alineadas con IFC/gbXML (GUID, condición de frontera); escenario = base + medidas; se agregan energía y costos; horario en CSV aparte | El usuario pidió que los datos se pudieran sacar de Revit y que el foco fuera el tradeoff confort–energía |
| v3 | Solo confort: se quitaron energía, costos, materiales por capa (densidad, material_id), envolvente y vanos detallados. Se dejaron los 6 factores de ASHRAE 55 y el método adaptativo | El usuario aclaró que el análisis es de confort y que solo importa lo que cambia el confort según ASHRAE |
| v4 | Agregación temporal (hora → día → mes → año); tabla final con T_op, energía y carbono para mes caliente, mes frío y año | El usuario pidió esos indicadores. Energía y carbono vuelven, pero como **resultados**, no como insumos |
| v5 | **Un solo CSV** en formato largo (escenario × periodo × espacio), autosuficiente | El usuario quiere manejarlo todo con un archivo que se pase directo al dashboard |
| v6 | Sin filas diarias; en TOTAL los extremos son el máx/mín entre cuartos (no promedio); se agregan cuarto y mes del extremo, y exceso/déficit máximo sobre los límites ASHRAE | Los máximos y mínimos ya muestran los casos límite, que es donde hay más problemas de confort |
| v7 | **Vivienda de una sola zona.** Se eliminan `espacios.csv`, `espacio_id`, `espacio_nombre`, `espacio_T_op_max/min`, la fila TOTAL, la ponderación por área y `evaluar_confort`. Una fila = escenario × periodo. El horario trae una sola serie para toda la vivienda; `area_m2` y `horario_ocupado` pasan a la config | El usuario pidió simplificar el modelo: generalizar las condiciones de las habitaciones y reducir los datos necesarios |
| v8 | **Solo extremos, sin horas.** Se eliminan horas_*, pct_confort, grados-hora, ocupación (`ocupado`, `horario_ocupado`), HR, promedios (T_op_prom, T_ext_prom), T_ext_media_predominante, T_confort, desglose de energía, delta_pct_confort_pp, delta_carbono_pct, metodo_confort (constante), clo, met, area_m2 y los factores de emisión repetidos por fila. Los límites ASHRAE se reportan en la hora del extremo. 54 → 32 columnas | El usuario indicó que no importan las horas, solo el máximo y el mínimo, y que hay que reducir variables |
| v8.1 | **Vuelve la humedad**, solo como extremos: `HR_max_pct` y `HR_min_pct` por periodo, de `HR_pct` del horario. 32 → 34 columnas | El usuario aclaró que el objetivo de la simulación es temperatura y humedad operativa, y pidió que la humedad regrese |
| v9 | **T_op del simulador, un valor por periodo.** El simulador (alimentado con los parámetros de `escenarios.csv`) entrega T_op y HR por mes (y anual) en `resultados_<escenario>.csv`, que sustituye al horario. Se eliminan T_op_max/min, mes_T_op_max/min, HR_max/min, delta_T_op_max/min, el cálculo de T_op desde aire + radiante y `dias_media_exterior`. Entran T_operativa_C, HR_pct, T_ext_media_C y delta_T_operativa_C. Los límites ASHRAE son del mes (t_pma = media exterior mensual); el año no tiene límite propio y su exceso/déficit es el del peor mes. Solo la T exterior conserva máx/mín. Clima por `--epw` o `--clima` mensual. 34 → 30 columnas | El usuario aclaró que la temperatura operativa sale de un simulador preciso a partir de los datos del Excel y que no es algo de máximos y mínimos; solo la exterior necesita máximo y mínimo |
| v10 (vigente) | **Solo variables que influyen.** Se eliminan `sombreado_m` (ninguna fórmula lo usa; en PUE-01 solo la fachada norte está expuesta y las ventanas son ~10 % del muro), `HR_pct` (no entra en ASHRAE 55 adaptativo) y `nivel` (se deduce de `periodo`). `delta_T_operativa_C` se sustituye por `delta_fuera_rango_C` (Δ de exceso + déficit contra el base: negativo = mejora), porque un ΔT_op no dice si el cambio es bueno. 9 → 8 parámetros, 30 → 27 columnas. El dashboard muestra qué medidas cambian contra el base | El usuario pidió reducir las variables que no influyen en el protocolo de datos |

**Principios que quedaron fijos:**
1. **Solo lo que cambia el confort.** Los parámetros de escenario son propiedades del elemento completo (U, SHGC, absortancia, ventilación, velocidad del aire), no sus materiales por capa. Una columna que no entra en ningún cálculo ni cambia la lectura no se agrega (v10).
2. **Escenario = estado completo de la casa.** Cada fila trae todos los parámetros, no solo el que cambió.
3. **Sin horas y sin recalcular al simulador.** No se cuentan horas. La T_op es la que da el simulador por periodo; el script no las promedia ni las reduce. Solo el clima exterior se reporta con máximo y mínimo.
4. **Un solo CSV, sin uniones entre tablas.** El dashboard filtra por `periodo` y `escenario_id`.
5. **No inventar.** Sin dato, la celda queda vacía y se anota en el log.
6. **ASHRAE 55 siempre.** Ningún otro criterio de confort sustituye al estándar; PMV/PPD, si se agrega, es complementario.
7. **Pensado para arquitectura.** Cada decisión de esquema se juzga por si una persona de arquitectura puede comparar medidas y sus tradeoffs de confort sin ayuda técnica.

## 4. Esquema vigente (v10, 27 columnas)

**Una fila = escenario × periodo** (la vivienda es una sola zona).
- Periodos `clave`: anual, mes_caliente, mes_frio.
- Periodos `mes`: ene…dic.
- Filas = escenarios × 15.

| Grupo | Columnas |
|---|---|
| Identificación | vivienda_id, escenario_id, escenario_nombre, es_base |
| Escenario | U_muro_ext, U_techo, U_ventana, SHGC_ventana, absortancia_muro, absortancia_techo, ventilacion_ach, vel_aire_m_s |
| Tiempo | periodo (anual, mes_caliente, mes_frio, ene…dic), mes |
| Clima exterior | T_ext_max_C, T_ext_min_C, T_ext_media_C (la media es la t_pma del mes) |
| Temp. operativa | T_operativa_C (del simulador) |
| Límites ASHRAE 55 y margen | limite_sup_C, limite_inf_C (del mes; vacíos en `anual`), exceso_sobre_limite_C, deficit_bajo_limite_C (en `anual`: el del peor mes) |
| Energía y carbono | energia_total_kWh, carbono_kgCO2e |
| Contra el base | delta_fuera_rango_C (Δ de exceso + déficit; negativo = mejora), delta_energia_pct |
| Supuestos | aceptabilidad_pct |

La tabla resumen que pidió el usuario (T_op, carbono y energía para mes caliente, mes frío y año) se obtiene filtrando `periodo` en `anual`, `mes_caliente` y `mes_frio`. Esas tres filas repiten datos de las mensuales: nunca se suman con ellas.

**Formato:** UTF-8, coma, punto decimal, snake_case sin acentos, unidad en el nombre, celda vacía = sin dato.

## 5. Lógica de cálculo

```
Usuario/archivos  → escenarios (8 parámetros) + config (supuestos)
Simulador         → por mes (y anual), punto central: T_operativa, energía
EPW o clima.csv   → por mes: T_ext máx, mín y media (media = t_pma del mes)
Script            → límites adaptativos del mes → exceso/déficit = T_op − límite
                  → año: T_op anual del simulador, exceso/déficit del peor mes, energía = suma de meses
                  → mes caliente / mes frío = copia del mes → deltas
```

**Método adaptativo (ASHRAE 55):**
- T_op la da el simulador (no se calcula en el script).
- t_pma = media exterior del mes (equivale al tope de 30 días de ASHRAE 55, coherente con un valor de T_op por mes).
- T_confort = 0.31·t_pma + 17.8, con banda ±3.5 °C (80 %) o ±2.5 °C (90 %).
- Válido solo con t_pma entre 10 y 33.5 °C; fuera de ese rango ese mes queda sin límites ni exceso/déficit (aviso en el log).
- Por velocidad del aire (`vel_aire_m_s` del escenario), el límite superior sube +1.2 / +1.8 / +2.2 °C con 0.6 / 0.9 / 1.2 m/s, cuando T_op > 25 °C.

**Mes caliente y mes frío:** el mes con la media exterior mensual más alta y la más baja, según el clima usado.

**Zona única:** la T_op es la del punto central que entrega el simulador. La energía es la de toda la vivienda. Si el simulador entrega varios cuartos, el usuario (o un paso previo fuera del script) los reduce a un solo valor antes de usar el script; el script no promedia cuartos.

**Energía:** cargas para mantener la casa dentro de los límites ASHRAE (cargas ideales). Si el simulador da carga térmica, solo se convierte a eléctrica con un COP o eficiencia dados. La T_op y la energía salen de **dos corridas distintas** del mismo modelo: la T_op de una corrida sin climatización (libre evolución), que es la que evalúa el método adaptativo, y la energía de una corrida con cargas ideales (ver `metodologia_calculo.md`, supuesto 2).

**Carbono:** solo de operación (energía × factor de emisión dado). Su delta contra el base es igual al de energía, por eso solo existe `delta_energia_pct`.

## 6. Decisiones confirmadas por el usuario

- Una vivienda de trabajo (PUE-01), superficie constante, varios cambios. El esquema admite más viviendas (`vivienda_id`).
- Los datos deben poder sacarse de Revit y de otras herramientas. Del modelo de Revit solo sirve, por ahora, la geometría (pendiente 8).
- Enfoque en confort según ASHRAE 55, sin propiedades de materiales por capa.
- Indicadores clave: T_op, energía y carbono para mes caliente, mes frío y año, junto con el confort.
- Un solo CSV que pasa directo al dashboard.
- Sin filas diarias ni horarias: el año, el mes caliente, el mes frío y cada mes cubren los casos que interesan.
- No importan las horas (de confort, ocupadas, etc.); hay que reducir variables (v8).
- La T operativa sale de un simulador preciso con los datos del Excel de escenarios, un valor por periodo; no se reporta como máximo y mínimo. Solo la T exterior lleva máximo y mínimo. Desde v10 no se reporta humedad ni volado, y el Δ de confort contra el base es el de grados fuera del rango (v10).
- Se aceptaron los valores por defecto: energía = cargas ideales hasta los límites ASHRAE; carbono solo de operación; la vivienda se evalúa como una sola zona (v7), por lo que ya no se decide qué cuartos evaluar.

## 7. Pendientes y preguntas abiertas

1. **Simulador:** confirmar cuál se usa (se menciona DesignBuilder), los nombres exactos de las columnas de salida y **qué estadístico es la T_op mensual que entrega** (media del mes u otro). El script la toma tal cual. Si no entrega fila anual, la T_op anual queda vacía.
2. **Clima:** ya se puede obtener de una base de datos pública por ubicación y periodo (`clima_por_ubicacion.py`, ERA5-Land vía Open-Meteo). Para Tlaxcalancingo (San Andrés Cholula), 2015–2024, el mes más caliente es mayo (media 19.2 °C) y el más frío enero (14.5 °C); NASA POWER difiere −0.14 °C en promedio. Falta decidir el periodo oficial del proyecto (p. ej. los últimos 10 años completos) o usar un EPW de una base pública.
3. **Valores base de construcción:** confirmar en campo los U, SHGC y absortancias de PUE-01 (hoy son rangos).
4. **Escenarios:** definir la lista de medidas y sus valores (los de los ejemplos eran ilustrativos).
5. **Factor de emisión y COP:** que el usuario dé el factor oficial vigente de la red eléctrica y, si aplica, el COP/eficiencia de los equipos.
6. **Ocupación:** desde v8 no se usa. Si más adelante se quiere ignorar horas sin gente, tendría que resolverlo el simulador al entregar la T_op del periodo.
7. **Cómo se generaliza la zona única:** definir cómo obtiene el simulador el valor de la vivienda (un solo nodo térmico, o promedio ponderado por área hecho antes del script).
8. **Modelo de Revit (`PUE-01_Diana.ifc`, revisado en noviembre de 2026):** los valores térmicos que trae son por defecto de Revit y no pueden usarse como parámetros de escenario: U de ventanas 3.69 W/m²K (≈ 0.65 Btu/h·ft²·°F, número imperial redondo; el vidrio sencillo estimado es ~5.8), U de una losa = 80 W/m²K (imposible), absortancia 0.7 en los tipos "Por defecto" y sin U en muros ni techos. Los 29 muros son de un solo material ("Yeso", 15 cm, sin capas) y todos están marcados como exteriores (293 m², contra ~96 m² expuestos). Los espacios suman 345 m² netos, contra 185.4 m² acondicionados. Además, el emplazamiento del IFC es el de por defecto de Revit ("Default", Madrid 40.42, −3.71, dirección de ejemplo): la ubicación debe salir de la dirección real. Corregir el modelo (capas reales, `IsExternal`, espacios, emplazamiento) antes de usarlo para la simulación o para carbono incorporado. El gbXML y los Excel del zip no están en el equipo de trabajo.

## 8. Mejoras futuras pensando en el dashboard final

- **PMV/PPD como método secundario:** para espacios con equipo de clima, agregar una columna `PPD_pct` por periodo (sin horas).
- **Carbono incorporado:** si se quiere el tradeoff completo, agregar `carbono_incorporado_kgCO2e` por escenario (necesita un factor por material con su fuente, dado por el usuario). Los volúmenes del IFC servirían una vez corregido el modelo (pendiente 8).
- **Costo:** `costo_inversion_MXN` y `retorno_simple_anios` si después se evalúa la viabilidad económica.
- **Varias viviendas:** ya funciona: un CSV por vivienda en `datos/` y el dashboard las une (hoy PUE-01 y PUE-02, ambas mock). Falta tener modelos reales; ese es el camino hacia los arquetipos del índice SECIHTI.
- **Versionado del esquema:** agregar una columna `version_esquema` para que el dashboard detecte archivos viejos.
- **Validación automática:** un script `validar_csv.py` con los chequeos de la skill (rangos, un solo base, filas esperadas).
- **Cuartos de nuevo (si hiciera falta):** el modelo de v6 con `espacio_id` y fila TOTAL queda en el historial; reintroducirlo implicaría volver a agregar `espacios.csv` y la ponderación por área.
- **Vistas actuales del dashboard** (filtros: vivienda, periodo `clave` y escenario de la gráfica mensual):
  1. Lectura rápida: escenarios dentro del rango, el más fuera del rango, mayor ahorro de energía y clima del periodo.
  2. Tabla de escenarios con todos los valores y qué medidas cambian contra el base (en pantallas angostas, una ficha por escenario). El rango ASHRAE 55 se muestra una sola vez por periodo, porque depende solo del clima del mes; en un escenario solo se indica si su ventilador sube el límite superior.
  3. T_op de cada escenario frente a la franja ASHRAE 55 del mes (se oculta en «Año», que no tiene franja propia).
  4. Tradeoff: grados fuera del rango contra energía, con el nombre de cada escenario junto a su punto.
  5. Mapa mes a mes: escenarios × meses; exceso en rojo y déficit en azul (paleta divergente con gris neutro = dentro del rango), intensidad relativa al mayor valor de la vivienda; un clic en una fila elige ese escenario para el detalle mensual.
  6. Mes a mes: T_op del escenario y del base contra la franja, con T exterior máx/mín de referencia.

## 9. Glosario corto

- **T_op (temperatura operativa):** combina la temperatura del aire y la de las superficies; es la que "siente" la persona.
- **t_pma (media exterior predominante):** promedio de la temperatura exterior de los días previos (aquí, la media del mes); es la base del método adaptativo.
- **Método adaptativo:** criterio de ASHRAE 55 para espacios ventilados naturalmente; la temperatura aceptable se ajusta al clima reciente.
- **Rango aceptable (límites ASHRAE 55):** franja de T_op en la que la mayoría está a gusto; cambia con el clima de cada mes.
- **Exceso / déficit:** grados por encima o por debajo de esa franja; 0 = dentro del rango.
- **Cargas ideales:** energía que necesitaría un equipo perfecto para mantener la casa en confort; sirve para comparar escenarios.
- **Medianera:** muro compartido con un vecino; se modela sin intercambio de calor (adiabático).
