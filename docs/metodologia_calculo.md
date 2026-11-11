# Metodología de cálculo del confort térmico

Este documento explica **qué fórmulas usa** `backend/generar_csv_confort.py`, **en qué orden**, **de dónde vienen** y **qué límites tiene** la implementación. Cada paso indica la función del script que lo hace.

## 1. Norma y dependencias

### Norma

- **ANSI/ASHRAE Standard 55, *Thermal Environmental Conditions for Human Occupancy*. Modelo de confort adaptativo** (sección 5.4 en la edición 2020: espacios naturalmente acondicionados y controlados por el ocupante).
- Los números de sección corresponden a la edición 2020. Los coeficientes del modelo adaptativo (0.31, 17.8, ±2.5/±3.5 °C, 10–33.5 °C y los escalones por velocidad del aire) son los mismos en las ediciones 2017 y 2020. Si se usa otra edición, hay que revisar que no hayan cambiado.

**Siempre se usa ASHRAE 55 adaptativo.** El método no es configurable.

**La temperatura operativa no se calcula en el script.** La entrega un simulador preciso, alimentado con los parámetros de cada escenario, como **un valor por mes** (y, si lo da, uno anual). El script la toma tal cual y solo la compara con los límites de ASHRAE 55.

### Dependencias

| Paquete | Para qué | ¿Hace cálculos de confort? |
|---|---|---|
| `pandas` | leer CSV, agrupar el EPW por mes | No |
| `numpy` | operaciones numéricas y condiciones (`np.where`, `np.clip`) | No |
| `pythermalcomfort` (solo desarrollo) | **verificar** que nuestras fórmulas den lo mismo que una implementación de referencia | Sí, pero **no se usa en el cálculo** |

Las fórmulas de ASHRAE 55 están **escritas directamente en el script**; no dependen de ninguna librería de confort. Así el cálculo queda a la vista y no cambia si una librería se actualiza.

**Verificación independiente.** `backend/pruebas/validar_ashrae55.py` compara la función `limites` con **pythermalcomfort** (Center for the Built Environment, UC Berkeley; probado con la versión 4.7.0) en 5 000 casos aleatorios: límites inferior y superior al 80 % y al 90 %, con velocidades del aire de 0.1 a 1.2 m/s (como la T_op viene dada, se pasa a pythermalcomfort con *t_a* = *t̄_r* = *t_o*). **Resultado: diferencia máxima de 0.0000 °C en todos los casos.**

```bash
pip install -r backend/requirements-dev.txt
python backend/pruebas/validar_ashrae55.py
```

Documentación de pythermalcomfort: <https://pythermalcomfort.readthedocs.io/> (función `adaptive_ashrae`). Herramienta web equivalente del CBE: <https://comfort.cbe.berkeley.edu/>.

## 2. Entradas que usa el cálculo

**Resultados del simulador** (`archivo_resultados` de cada escenario), una fila por mes (`mes` = 1–12 o ene–dic) y, opcional, una fila `mes = anual`, del **punto central de la vivienda** (una sola zona):

| Símbolo | Columna | Unidad | Obligatoria |
|---|---|---|---|
| *t_o* | `T_operativa_C` | °C | sí |
| — | `energia_enfriamiento_kWh`, `energia_calefaccion_kWh` | kWh | no |

**Clima** (`--epw` horario, o `--clima` con una fila por mes):

| Símbolo | Columna | Unidad | De dónde sale con EPW |
|---|---|---|---|
| — | `T_ext_max_C`, `T_ext_min_C` | °C | máximo y mínimo horario del mes |
| *t_ext,mes* | `T_ext_media_C` | °C | promedio horario del mes |

**Escenario:** `vel_aire_m_s` (*V*), para el ajuste del límite superior. Los otros 7 parámetros (valores U, SHGC, absortancias, ventilación) **describen** el escenario y alimentan al simulador, pero **no entran en ninguna fórmula del script**: su efecto ya está en la *t_o* que entrega el simulador.

**Configuración** (`config.csv`): `aceptabilidad_pct` (80 o 90), `energia_tipo`, `COP_enfriamiento`, `eficiencia_calefaccion` y `factor_emision_kgCO2e_kWh`.

## 3. Paso a paso

### Paso 1. Clima por periodo — función `leer_clima`

- **Con EPW:** para cada mes, máximo, mínimo y promedio de las 8 760 temperaturas horarias; para el año, lo mismo sobre todas las horas.
- **Con `clima.csv`:** se toman los valores tal cual. Si no trae fila `anual`, el año usa el máximo y el mínimo de los meses, y la media **ponderada por los días de cada mes** (es el promedio exacto del año si las medias mensuales son promedios de todas las horas). Se anota como supuesto en el log.

### Paso 2. Temperatura media exterior predominante, *t_pma* — `main`

ASHRAE 55 (5.4.2.1) define *t_pma* como la media de la temperatura exterior de entre **7 y 30 días** previos. Como el simulador entrega **un valor de *t_o* por mes**, se usa la **media exterior de ese mismo mes**:

$$
t_{pma}(\text{mes}) = t_{ext,mes}
$$

Es la ventana de ~30 días, el tope que permite la norma, y coincide en el tiempo con la *t_o* mensual. Se anota como supuesto en el log.

- **Mes caliente / mes frío:** el mes con la *t_ext,mes* más alta o más baja.

### Paso 3. Temperatura de confort, *t_cmf* — función `limites`

ASHRAE 55, 5.4.2:

$$
t_{cmf} = 0.31\,t_{pma} + 17.8
$$

### Paso 4. Límites de aceptabilidad — función `limites` (con `extra_vel`)

| `aceptabilidad_pct` | Banda Δ |
|---|---|
| 80 | 3.5 °C |
| 90 | 2.5 °C |

$$
\text{límite inferior} = t_{cmf} - \Delta
$$

$$
\text{límite superior} = t_{cmf} + \Delta + \Delta_V \qquad (\Delta_V \text{ solo si } t_o > 25\ ^\circ\text{C})
$$

**Ajuste por velocidad del aire, Δ_V** (ASHRAE 55, 5.4.2.4). Solo sube el límite superior, y solo si la *t_o* del mes es mayor a 25 °C. Usa `vel_aire_m_s` del escenario:

| *V* | Δ_V |
|---|---|
| *V* < 0.6 m/s, o sin dato | 0 |
| 0.6 ≤ *V* < 0.9 m/s | +1.2 °C |
| 0.9 ≤ *V* < 1.2 m/s | +1.8 °C |
| *V* ≥ 1.2 m/s | +2.2 °C |

Se usan escalones, sin interpolar, igual que pythermalcomfort.

**Rango de aplicación:** el modelo adaptativo solo vale con **10 °C ≤ t_pma ≤ 33.5 °C**. Un mes fuera de ese rango queda sin límites ni exceso/déficit, y el log lo avisa.

**Detalles de configuración:**

- Si falta `aceptabilidad_pct`, no se calculan límites y el log lo marca como faltante.
- Cualquier valor distinto de 90 se trata como 80 % (banda de 3.5 °C).

### Paso 5. Exceso y déficit — `main`

Para cada mes:

$$
\text{exceso} = \max\big(0,\ t_o - \text{límite superior}\big)
\qquad
\text{déficit} = \max\big(0,\ \text{límite inferior} - t_o\big)
$$

El exceso mide cuántos grados por **encima** del rango aceptable está la casa (calor) y el déficit cuántos por **debajo** (frío). Dentro del rango, ambos valen 0.

### Paso 6. Filas por periodo — `main`

Periodos: `anual`, `mes_caliente`, `mes_frio` y cada mes (`ene` … `dic`). No se cuentan horas y la *t_o* no se promedia ni se reduce: es la del simulador.

| Columna | Mes (`ene`…`dic`, `mes_caliente`, `mes_frio`) | Año (`anual`) |
|---|---|---|
| `T_ext_max_C`, `T_ext_min_C`, `T_ext_media_C` | del clima del mes | del clima del año |
| `T_operativa_C` | fila del mes del simulador | fila `anual` del simulador; **vacía** si no la da (no se promedian meses) |
| `limite_sup_C`, `limite_inf_C` | pasos 3–4 | **vacíos**: el año no tiene un límite propio, cada mes tiene el suyo |
| `exceso_sobre_limite_C`, `deficit_bajo_limite_C` | paso 5 | el del **peor mes** (máximo de los 12); **vacío** si falta la *t_o* de algún mes |

`mes_caliente` y `mes_frio` son copias de la fila del mes correspondiente; `mes` dice cuál es.

### Paso 7. Energía y carbono — función `energia_total` y `main`

Según `energia_tipo` en la configuración:

- **`electrica`:** E = E_enf + E_cal, tal como vienen del simulador.
- **`termica`** (cargas ideales):

$$
E = \frac{E_{enf}}{COP} + \frac{E_{cal}}{\eta}
$$

  Si falta el COP o la eficiencia, la energía queda **vacía**. No se supone ningún valor.
- **Sin `energia_tipo`:** se suma tal como viene y el log lo avisa.

Después:

- `energia_total_kWh` del mes = *E* de esa fila. Del año = **suma de los 12 meses** si están todos; si falta alguno, la fila `anual` del simulador.
- `carbono_kgCO2e` = `energia_total_kWh` × `factor_emision_kgCO2e_kWh`. Solo carbono de operación; queda vacío si no se da el factor.

### Paso 8. Comparación contra el caso base — `main`

Se compara cada escenario con el escenario base (`es_base = Si`) **en el mismo periodo**:

$$
\Delta_{fuera} = (\text{exceso} + \text{déficit})^{esc} - (\text{exceso} + \text{déficit})^{base}
\qquad
\Delta E\,[\%] = 100\,\frac{E^{esc} - E^{base}}{E^{base}} \quad (\text{vacío si } E^{base} = 0)
$$

`delta_fuera_rango_C` = $\Delta_{fuera}$; queda vacío si falta el exceso o el déficit del escenario o del base.

No hay delta de carbono: con un solo factor de emisión sería idéntico al de energía.

Interpretación: un $\Delta_{fuera}$ **negativo** es mejora (el escenario queda más cerca del rango que el base), y un $\Delta E$ negativo es ahorro. Hasta v9 se reportaba $\Delta T_{op}$, que no dice si el cambio es bueno: subir la T_op ayuda en frío y perjudica en calor.

### Paso 9. Redondeo

Todos los valores numéricos se redondean a **2 decimales** al final, solo al escribir el CSV. Los cálculos intermedios no se redondean.

## 4. Ejemplo numérico

**Datos del mes (mayo).** Media exterior del mes 18.9 °C. Aceptabilidad del 80 %. El simulador da *t_o* = 28.8 °C. El escenario tiene ventilador con *V* = 0.9 m/s.

| Paso | Cálculo | Resultado |
|---|---|---|
| 2. *t_pma* | media exterior de mayo | 18.90 °C |
| 3. *t_cmf* | 0.31·18.9 + 17.8 | 23.66 °C |
| 4. límite inferior | 23.66 − 3.5 | 20.16 °C |
| 4. Δ_V | *t_o* > 25 y 0.9 ≤ *V* < 1.2 | +1.8 °C |
| 4. límite superior | 23.66 + 3.5 + 1.8 | 28.96 °C |
| 5. exceso | máx(0, 28.8 − 28.96) | **0 °C** |
| 5. déficit | máx(0, 20.16 − 28.8) | 0 °C |

Con el ventilador, mayo queda dentro del rango. Sin él (*V* < 0.6 m/s) el límite superior sería 27.16 °C y el exceso subiría a 1.64 °C.

**Energía** (`energia_tipo = termica`, COP = 3, η = 0.9, factor = 0.435 kgCO₂e/kWh). Con 10 kWh de enfriamiento y 4 kWh de calefacción en el mes:

- E = 10/3 + 4/0.9 = 3.33 + 4.44 = 7.78 kWh
- Carbono = 7.78 × 0.435 = 3.38 kgCO₂e

## 5. Supuestos y limitaciones

1. **Condiciones para usar el modelo adaptativo.** ASHRAE 55 lo permite solo en espacios naturalmente acondicionados, sin enfriamiento mecánico en operación, con ocupantes de actividad sedentaria (≈ 1.0–1.3 met) que pueden ajustar su ropa y abrir ventanas. **El script no verifica estas condiciones;** se supone que la vivienda las cumple.
2. **Temperatura de libre evolución frente a cargas ideales.** Para que el confort adaptativo tenga sentido, la *t_o* debe venir de una simulación **sin climatización** (libre evolución). Si la energía se obtiene con cargas ideales que mantienen la casa en un rango, esa corrida debe ser **otra** distinta a la de temperaturas. Hay que confirmarlo al definir la simulación.
3. **Un valor por mes.** Lo que represente la *t_o* mensual (media del mes u otro estadístico) lo define el simulador; el script no la transforma. Un valor mensual no muestra los días u horas más extremos dentro del mes: un mes puede quedar "dentro del rango" aunque tenga tardes fuera de él.
4. **t_pma = media exterior del mes**, en lugar de una media móvil de 7–30 días previos (ver paso 2).
5. **Una sola zona.** Se idealiza toda la vivienda con un punto central. No se capturan diferencias entre cuartos ni cerca de muros y ventanas.
6. **Velocidad del aire.** Se usa la del escenario (constante), en escalones sin interpolar.
7. **Humedad.** No afecta los límites del modelo adaptativo, así que desde v10 no se reporta; si el simulador entrega `HR_pct`, el script la ignora.
8. **Exceso/déficit en el dashboard.** La gráfica de *tradeoff* suma `exceso_sobre_limite_C + deficit_bajo_limite_C` como un solo indicador de qué tan fuera del rango queda la vivienda. Esa suma la hace el dashboard, no está en el CSV.

## 6. Mapa función → paso

| Función en `backend/generar_csv_confort.py` | Pasos |
|---|---|
| `leer_clima` (con `leer_epw`) | 1 |
| `limites` | 3, 4 |
| `extra_vel` | 4 (Δ_V) |
| `energia_total` | 7 |
| `main` | t_pma y mes caliente/frío (2), exceso/déficit (5), filas por periodo (6), energía anual y carbono (7), deltas (8), redondeo (9) |
