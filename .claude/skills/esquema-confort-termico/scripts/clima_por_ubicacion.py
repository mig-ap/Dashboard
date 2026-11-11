#!/usr/bin/env python3
"""
clima_por_ubicacion.py — Temperatura exterior mensual (máx, mín, media) de una base de datos pública,
a partir de la ubicación y un periodo. No usa simulación del proyecto: el dato sale de una base
consultable por cualquiera con la misma URL. Solo usa la biblioteca estándar de Python.

Fuente principal: Open-Meteo Historical Weather API (https://open-meteo.com/en/docs/historical-weather-api),
que sirve el reanálisis ERA5 / ERA5-Land de ECMWF (observaciones asimiladas, hora por hora).
Contraste opcional: NASA POWER (https://power.larc.nasa.gov), promedios mensuales de MERRA-2.
Ubicación por nombre: Open-Meteo Geocoding API (datos de GeoNames). Si el nombre es ambiguo,
el script se detiene y lista los candidatos: nunca escoge uno por su cuenta.

Uso:
  python clima_por_ubicacion.py --lugar Tlaxcalancingo --municipio "San Andrés Cholula" --desde 2015 --hasta 2024
  python clima_por_ubicacion.py --lat 19.0147 --lon -98.2631 --desde 2024-01-01 --hasta 2024-12-31 [--verificar-nasa]
Escribe (por defecto en la carpeta actual):
  clima.csv               mes, T_ext_max_C, T_ext_min_C, T_ext_media_C (12 meses + anual), listo para generar_csv_confort.py
  clima_fuente.json       URL exacta, modelo, punto, fecha de consulta y completitud
  trazabilidad_clima.csv  filas de trazabilidad (origen = base_de_datos, estado = confirmado)
Con varios años, cada mes junta todas sus horas de todos los años: la media es el promedio de esas
horas y el máximo/mínimo son los extremos del periodo completo.
"""
import argparse, csv, datetime as dt, json, os, sys, unicodedata, urllib.parse, urllib.request

sys.stdout.reconfigure(errors="backslashreplace")
TRAZA = ["escenario_id", "campo", "valor", "unidad", "origen", "fuente", "estado", "nota"]
GEO = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVO = "https://archive-api.open-meteo.com/v1/archive"
NASA = "https://power.larc.nasa.gov/api/temporal/monthly/point"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

def pedir(url, params):
    completa = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(completa, headers={"User-Agent": "esquema-confort-termico/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r), completa
    except Exception as e:
        sys.exit(f"No se pudo consultar {completa}\n  {e}\n  Sin red: abre esa URL en un navegador, guarda el JSON y avisa a quien opera la skill.")

def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")

def ubicar(a):
    if a.lat is not None and a.lon is not None:
        return {"latitud": a.lat, "longitud": a.lon, "nombre": a.lugar or "coordenadas dadas", "zona": a.zona or "auto",
                "fuente": "coordenadas dadas por la persona usuaria"}
    if not a.lugar:
        sys.exit("Falta la ubicación: usa --lugar (y --municipio/--estado si hace falta) o --lat y --lon.")
    datos, url = pedir(GEO, {"name": a.lugar, "count": 20, "language": "es", "format": "json"})
    cand = datos.get("results") or []
    for filtro, campos in [(a.pais, ["country_code", "country"]), (a.estado, ["admin1"]), (a.municipio, ["admin2", "admin3"])]:
        if filtro:
            cand = [c for c in cand if any(sin_acentos(filtro) in sin_acentos(c.get(k)) for k in campos)]
    if len(cand) != 1:
        print(f"{'Ningún' if not cand else len(cand)} resultado(s) para '{a.lugar}' con esos filtros ({url}):")
        for c in cand:
            print(f"  - {c['name']} · {c.get('admin2', '')}, {c.get('admin1', '')}, {c.get('country', '')} · lat {c['latitude']}, lon {c['longitude']}, {c.get('elevation')} m")
        sys.exit("Ubicación ambigua o no encontrada: precisa con --municipio/--estado/--pais o da --lat y --lon. No se escoge un candidato por adivinanza.")
    c = cand[0]
    return {"latitud": c["latitude"], "longitud": c["longitude"], "elevacion_m": c.get("elevation"), "zona": a.zona or c.get("timezone", "auto"),
            "nombre": f"{c['name']}, {c.get('admin2', '')}, {c.get('admin1', '')}, {c.get('country', '')}", "fuente": url}

def fechas(desde, hasta):
    d = dt.date.fromisoformat(desde) if len(desde) > 4 else dt.date(int(desde), 1, 1)
    h = dt.date.fromisoformat(hasta) if len(hasta) > 4 else dt.date(int(hasta), 12, 31)
    limite = dt.date.today() - dt.timedelta(days=7)   # el archivo se publica con unos días de retraso
    if h > limite:
        sys.exit(f"--hasta {h} es demasiado reciente; el último día disponible es aprox. {limite}.")
    if d > h:
        sys.exit("--desde es posterior a --hasta.")
    return d, h

def main():
    ap = argparse.ArgumentParser(description="Clima mensual desde una base de datos pública, por ubicación y periodo.")
    ap.add_argument("--lugar"); ap.add_argument("--municipio"); ap.add_argument("--estado"); ap.add_argument("--pais")
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--desde", required=True, help="AAAA o AAAA-MM-DD"); ap.add_argument("--hasta", required=True)
    ap.add_argument("--modelo", default="era5_land", help="modelo de Open-Meteo (era5_land, era5, …)")
    ap.add_argument("--zona", help="zona horaria IANA; por defecto la del lugar")
    ap.add_argument("--salida", default=".")
    ap.add_argument("--verificar-nasa", action="store_true", help="compara las medias mensuales con NASA POWER")
    a = ap.parse_args()
    d, h = fechas(a.desde, a.hasta)
    u = ubicar(a)
    params = {"latitude": u["latitud"], "longitude": u["longitud"], "start_date": d.isoformat(), "end_date": h.isoformat(),
              "hourly": "temperature_2m", "models": a.modelo, "timezone": u["zona"]}
    datos, url = pedir(ARCHIVO, params)
    horas, temps = datos["hourly"]["time"], datos["hourly"]["temperature_2m"]
    por_mes = {m: [] for m in range(1, 13)}
    esperadas = {m: 0 for m in range(1, 13)}
    for t, v in zip(horas, temps):
        m = int(t[5:7]); esperadas[m] += 1
        if v is not None:
            por_mes[m].append(v)
    faltan = [MESES[m - 1] for m in range(1, 13) if not por_mes[m]]
    if faltan:
        sys.exit(f"El periodo no cubre todos los meses (faltan {', '.join(faltan)}): usa al menos un año completo.")
    incompletos = [f"{MESES[m - 1]} ({len(por_mes[m]) / esperadas[m]:.0%})" for m in range(1, 13) if len(por_mes[m]) < 0.9 * esperadas[m]]
    todas = [v for m in range(1, 13) for v in por_mes[m]]
    filas = [(m, max(por_mes[m]), min(por_mes[m]), sum(por_mes[m]) / len(por_mes[m])) for m in range(1, 13)]
    filas.append(("anual", max(todas), min(todas), sum(todas) / len(todas)))
    os.makedirs(a.salida, exist_ok=True)
    with open(os.path.join(a.salida, "clima.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["mes", "T_ext_max_C", "T_ext_min_C", "T_ext_media_C"])
        w.writerows([m, round(x, 2), round(n, 2), round(me, 2)] for m, x, n, me in filas)

    consulta = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    fuente = {"base_de_datos": f"Open-Meteo Historical Weather API, modelo {a.modelo} (reanálisis ECMWF)", "url": url,
              "ubicacion": u, "punto_del_modelo": {"latitud": datos.get("latitude"), "longitud": datos.get("longitude"), "elevacion_m": datos.get("elevation")},
              "periodo": [d.isoformat(), h.isoformat()], "zona_horaria": datos.get("timezone"), "horas": len(todas),
              "meses_incompletos": incompletos, "consultado": consulta,
              "agregacion": "por mes: máximo, mínimo y promedio de todas las horas de ese mes en el periodo; anual: de todas las horas"}
    nota = f"{u['nombre']}; punto {datos.get('latitude')}, {datos.get('longitude')}, {datos.get('elevation')} m; {d}…{h}; consultado {consulta}"

    if a.verificar_nasa:
        nasa, url_n = pedir(NASA, {"parameters": "T2M", "community": "RE", "latitude": u["latitud"], "longitude": u["longitud"],
                                   "start": d.year, "end": h.year, "format": "JSON"})
        t2m = nasa["properties"]["parameter"]["T2M"]
        dif = []
        for m in range(1, 13):
            vals = [v for k, v in t2m.items() if k[4:] == f"{m:02d}" and v > -900 and d <= dt.date(int(k[:4]), m, 1) <= h]
            if vals:
                dif.append(filas[m - 1][3] - sum(vals) / len(vals))
        fuente["contraste_nasa_power"] = {"url": url_n, "diferencia_media_C": round(sum(dif) / len(dif), 2) if dif else None,
                                          "diferencia_max_abs_C": round(max(map(abs, dif)), 2) if dif else None,
                                          "nota": "MERRA-2 a ~0.5°: en terreno montañoso puede diferir por la elevación del punto"}
        print(f"  contraste NASA POWER: diferencia media {fuente['contraste_nasa_power']['diferencia_media_C']} °C, "
              f"máxima {fuente['contraste_nasa_power']['diferencia_max_abs_C']} °C")
    with open(os.path.join(a.salida, "clima_fuente.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(fuente, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.salida, "trazabilidad_clima.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, TRAZA, lineterminator="\n"); w.writeheader()
        w.writerow({"escenario_id": "", "campo": "ubicacion_lat_lon", "valor": f"{u['latitud']}, {u['longitud']}", "unidad": "°",
                    "origen": "base_de_datos" if u["fuente"].startswith("http") else "usuario", "fuente": u["fuente"],
                    "estado": "confirmado", "nota": u["nombre"]})
        for c, desc in [("T_ext_max_C", "máximo"), ("T_ext_min_C", "mínimo"), ("T_ext_media_C", "media")]:
            w.writerow({"escenario_id": "", "campo": c, "valor": "clima.csv (12 meses + anual)", "unidad": "°C", "origen": "base_de_datos",
                        "fuente": url, "estado": "confirmado", "nota": f"{desc} horario por mes; {nota}"})
    print(f"OK: clima.csv ({len(todas)} horas, {u['nombre']}) → {a.salida}")
    if incompletos:
        print("  aviso: meses con menos del 90 % de las horas:", ", ".join(incompletos))

if __name__ == "__main__":
    main()
