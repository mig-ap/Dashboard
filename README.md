# Dashboard de confort térmico

Herramienta para comparar **cambios a una vivienda** (aislamiento, vidrios, acabados, ventilación…) y ver cuánto mejoran el **confort térmico según ASHRAE 55**, y cuánto cuestan en **energía** y **carbono**. Está pensada para que una persona de arquitectura pueda leer los resultados sin conocimientos de simulación.

Proyecto de becario dentro del proyecto SECIHTI de descarbonización de vivienda en Puebla. Los datos incluidos (`PUE-01`, `PUE-02`) son **de prueba (mock)** y no representan casas reales.

## Qué hace

1. **Backend (`backend/`)**: toma los resultados del simulador de cada escenario (un valor por mes) y genera **un CSV por vivienda** con los indicadores de confort.
2. **Datos (`datos/`)**: aquí se guardan esos CSV. El dashboard lee **todos** los `.csv` de esta carpeta, sin importar cuántos sean ni de cuántas viviendas.
3. **Dashboard (`dashboard/`)**: página web que muestra, por vivienda y periodo (año, mes más caliente o mes más frío):
   - una lectura rápida: cuántos escenarios quedan dentro del rango, cuál queda más fuera, cuál ahorra más energía y el clima del periodo,
   - una guía para leer cada término,
   - una tabla con cada escenario frente al caso base y las medidas que lo distinguen,
   - la temperatura operativa de cada escenario frente a la franja aceptable de ASHRAE 55,
   - el *tradeoff* confort contra energía,
   - la evolución mes a mes del escenario elegido frente al base.

   Se ve completa en pantallas de computadora, tableta y celular.

## Cómo lo hace

- **Una vivienda = una zona.** Un simulador preciso, alimentado con los parámetros de cada escenario, entrega la temperatura operativa de **un punto central de la casa**, lejos de los muros, como **un valor por mes** (y uno anual). El script no calcula ni resume la temperatura operativa: la toma tal cual.
- **Solo el clima exterior lleva máximo y mínimo.** La T operativa es un solo valor por periodo. No se reporta humedad: no entra en ASHRAE 55 adaptativo.
- **ASHRAE 55, método adaptativo, siempre.** Con la temperatura exterior media del mes se calcula el rango aceptable de ese mes (banda de 80 % o 90 % de aceptabilidad; el límite superior sube si hay movimiento de aire) y cuánto se sale de él la T operativa (exceso/déficit). El año no tiene límite propio: su exceso/déficit es el del peor mes.
- **Comparación contra el base.** Cada escenario trae la diferencia contra el caso base en grados fuera del rango (negativo = mejora) y en energía.
- **No inventa datos.** Si falta un dato, la celda queda vacía y se anota en un log (`<archivo>_log.md`).

Una fila del CSV = escenario × periodo (15 filas por escenario). Documentación detallada:

- [`docs/metodologia_calculo.md`](docs/metodologia_calculo.md): **todas las fórmulas** (ASHRAE 55 adaptativo), paso a paso, con un ejemplo numérico, supuestos y limitaciones. Las fórmulas están escritas en el propio script; la única librería de confort, `pythermalcomfort`, solo se usa para verificarlas (`python backend/pruebas/validar_ashrae55.py`).
- [`docs/contexto_esquema_confort.md`](docs/contexto_esquema_confort.md): las 27 columnas y el historial de decisiones del esquema.

## Estructura

```
backend/
  generar_csv_confort.py   genera el CSV de una vivienda
  requirements.txt         dependencias (pandas, numpy)
  requirements-dev.txt     + pythermalcomfort, solo para verificar
  pruebas/                 validación de fórmulas contra pythermalcomfort
  mock/crear_mock.py       crea entradas de prueba
  importacion/             IFC/Revit y bases de datos → entradas del esquema (solo Python estándar)
datos/                     CSV que lee el dashboard (agrega aquí los tuyos)
dashboard/
  index.html               el dashboard
  servidor.py              servidor local (solo Python estándar)
docs/                      metodología de cálculo, contexto y decisiones
.claude/skills/            skill de Claude para importar datos y armar el esquema
herramientas/              utilidades (empaquetar la skill)
```

## Probarlo en tu equipo

Necesitas **Python 3.10 o superior** y un navegador. El dashboard carga sus librerías de gráficas desde internet, así que necesitas conexión.

### 1. Ver el dashboard (no requiere instalar nada)

```bash
git clone <url-del-repositorio>
cd Dahsboard_Thermal_Comfort
python dashboard/servidor.py
```

En Windows usa `py` en lugar de `python` si `python` no existe. Se abre `http://localhost:8000` con los datos de `datos/`. Si otro programa ya usa ese puerto, el servidor prueba solo el siguiente libre (8001, 8002…) y muestra en la terminal la dirección correcta. Para cerrar el servidor: `Ctrl+C`.

Opciones: `--puerto 8080` para otro puerto, `--datos otra/carpeta` para leer CSV de otra carpeta, `--sin-navegador` para no abrir el navegador.

> Sin servidor también puedes abrir `dashboard/index.html` con doble clic y usar **«Abrir CSV sin servidor»** para elegir uno o varios CSV a mano.

### 2. Agregar datos

Copia cualquier CSV generado por el backend a `datos/` y pulsa **«Recargar datos/»** (o recarga la página). Puedes tener tantos archivos como quieras; el selector **Vivienda** muestra todas las viviendas encontradas. Si el mismo escenario de la misma vivienda aparece en dos archivos, se usa el del archivo que va después en orden alfabético y el dashboard lo avisa. Los archivos que no tienen el formato esperado se omiten con un aviso.

### 3. Generar CSV con el backend

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

Con datos de prueba:

```bash
python backend/mock/crear_mock.py --vivienda PUE-03 --ajuste-clima 1
python backend/generar_csv_confort.py \
  --escenarios backend/mock/entradas/PUE-03/escenarios.csv \
  --config backend/mock/entradas/PUE-03/config.csv \
  --clima backend/mock/entradas/PUE-03/clima.csv \
  --salida datos/confort_PUE-03_mock.csv
```

Recarga el dashboard y aparecerá la vivienda `PUE-03`.

Con datos reales necesitas cuatro tipos de archivo (el formato completo está al inicio de `backend/generar_csv_confort.py`):

| Archivo | Quién lo llena | Contenido |
|---|---|---|
| `escenarios.csv` | a mano | un renglón por escenario: id, nombre, si es el base, archivo de resultados y los 8 parámetros de la medida (U de muro/techo/ventana, SHGC, absortancias, ventilación, velocidad del aire) |
| `config.csv` | a mano | `vivienda_id`, `aceptabilidad_pct` (80 o 90) y, si se tienen, factor de emisión y COP/eficiencias |
| `resultados_<escenario>.csv` | simulador | una fila por mes (`mes` = 1–12) y, si se tiene, una fila `anual`: `T_operativa_C` del punto central, energía de enfriamiento y calefacción |
| `clima.csv` (o un `--epw`) | clima | por mes: `T_ext_max_C`, `T_ext_min_C`, `T_ext_media_C` |

Revisa siempre el `_log.md` que se genera junto al CSV: dice qué quedó vacío y qué dato hace falta.

## Importar datos de Revit/IFC con Claude (skill)

La skill `esquema-confort-termico` le enseña a Claude a armar el esquema a partir de los archivos del proyecto **sin inventar datos**:

- **Del IFC** saca la geometría y señala lo que no sirve: ubicación y valores térmicos por defecto de Revit, U imposibles, muros sin capas.
- **El clima** lo obtiene de una base de datos pública según la ubicación y el periodo que elijas: reanálisis ERA5-Land vía Open-Meteo, con contraste opcional contra NASA POWER. Guarda la URL exacta para que cualquiera lo verifique.
- **Cada valor** queda en una trazabilidad con su origen, su fuente y su estado (confirmado, revisar o faltante). Lo que no tiene fuente se queda vacío y va a una lista de pendientes.
- **Nunca simula.** La temperatura operativa y la energía solo vienen de los resultados del simulador del proyecto.

**Instalarla en Claude Cowork o claude.ai:** genera el paquete con `python herramientas/empaquetar_skill.py` y sube `dist/esquema-confort-termico.skill` en la sección de Skills de la configuración de Claude. Después basta con pedir, por ejemplo: "importa este IFC y arma el esquema de confort de la vivienda".

**En Claude Code** la skill se activa sola al abrir esta carpeta.

Los scripts también se pueden usar a mano, desde `backend/importacion/`:

```bash
python backend/importacion/extraer_ifc.py modelo.ifc --salida trabajo/
python backend/importacion/clima_por_ubicacion.py --lugar Tlaxcalancingo --municipio "San Andrés Cholula" --desde 2015 --hasta 2024 --verificar-nasa --salida trabajo/
python backend/importacion/calcular_u.py capas_muro.csv --elemento muro
python backend/importacion/armar_entradas.py trazabilidad.csv trabajo/trazabilidad_ifc.csv trabajo/trazabilidad_clima.csv --salida trabajo/entradas/
```

Si cambias `backend/` o `docs/`, ejecuta `python herramientas/empaquetar_skill.py` para actualizar la copia de la skill.
