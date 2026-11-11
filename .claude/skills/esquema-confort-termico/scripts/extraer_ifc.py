#!/usr/bin/env python3
"""
extraer_ifc.py — Lee un IFC (exportado de Revit u otro programa) y separa lo que el archivo
sí dice de lo que solo parece decir. Solo usa la biblioteca estándar de Python.

Saca: ubicación del emplazamiento, espacios (área y volumen), muros, ventanas, losas y techos
(cantidades, materiales y capas) y las propiedades térmicas que traiga (U, SHGC, absortancia).
Cada propiedad térmica se marca "revisar" con el motivo cuando parece un valor por defecto
del programa (Revit pone valores genéricos) o es físicamente imposible. Ningún valor del IFC
se da por confirmado: los candidatos salen con estado "revisar" para que una persona decida.

Uso:  python extraer_ifc.py modelo.ifc [--salida carpeta]
Escribe en la carpeta de salida (por defecto, junto al IFC):
  ifc_resumen.json       todo lo extraído, con referencias #id al IFC
  ifc_hallazgos.md       resumen legible: qué sirve, qué no y por qué
  trazabilidad_ifc.csv   candidatos para el esquema (escenario_id = base, estado = revisar)
"""
import argparse, collections, csv, json, os, re, sys

sys.stdout.reconfigure(errors="backslashreplace")
TRAZA = ["escenario_id", "campo", "valor", "unidad", "origen", "fuente", "estado", "nota"]
BTU = 5.678263  # 1 Btu/(h·ft²·°F) en W/(m²·K)
POR_DEFECTO = re.compile(r"por defecto|default|gen[eé]ric|generic|introduzca|enter address", re.I)

# ---------- lector STEP (ISO 10303-21) ----------
def decodificar(s):
    """Texto IFC: '' → ', \\X\\hh (ISO 8859-1), \\X2\\hhhh…\\X0\\ (UTF-16)."""
    s = s.replace("''", "'")
    s = re.sub(r"\\X2\\((?:[0-9A-F]{4})+)\\X0\\", lambda m: bytes.fromhex(m.group(1)).decode("utf-16-be"), s)
    return re.sub(r"\\X\\([0-9A-F]{2})", lambda m: bytes.fromhex(m.group(1)).decode("latin-1"), s)

TOKEN = re.compile(r"'(?:[^']|'')*'|#\d+|\.[A-Z_]+\.|[A-Z][A-Z0-9_]*\(|[-+]?\d+\.?\d*(?:E[-+]?\d+)?|\$|\*|\(|\)|,", re.I)

def argumentos(texto):
    """Convierte los argumentos de una entidad en listas anidadas de Python."""
    pila, actual = [], []
    for t in TOKEN.findall(texto):
        if t == ",":
            continue
        if t == "(" or t.endswith("("):
            nuevo = [] if t == "(" else ["@" + t[:-1].upper()]   # valor con tipo: ['@IFCLABEL', 'x']
            actual.append(nuevo); pila.append(actual); actual = nuevo
        elif t == ")":
            actual = pila.pop() if pila else actual
        elif t[0] == "'":
            actual.append(decodificar(t[1:-1]))
        elif t[0] == "#":
            actual.append(("ref", int(t[1:])))
        elif t in ("$", "*"):
            actual.append(None)
        elif t[0] == ".":
            actual.append(t.strip("."))
        else:
            actual.append(float(t))
    return actual

def leer_ifc(ruta):
    with open(ruta, encoding="latin-1") as f:
        txt = f.read()
    cab = re.search(r"FILE_DESCRIPTION\s*\((.*?)\);", txt, re.S)
    ents = {}
    for m in re.finditer(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;\s*(?=#\d+\s*=|ENDSEC)", txt, re.S):
        ents[int(m.group(1))] = (m.group(2).upper(), argumentos(m.group(3)))
    esquema = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'", txt)
    origen = re.search(r"FILE_NAME\s*\((.*?)\);", txt, re.S)
    return ents, (decodificar(cab.group(1)) if cab else ""), (esquema.group(1) if esquema else "?"), (decodificar(origen.group(1)) if origen else "")

# ---------- utilidades sobre las entidades ----------
class Modelo:
    def __init__(self, ruta):
        self.ruta = ruta
        self.e, self.cabecera, self.esquema, self.origen = leer_ifc(ruta)
        self.psets = collections.defaultdict(list)      # objeto -> [pset]
        self.tipo_de = {}                               # ocurrencia -> tipo
        self.material_de = {}                           # objeto -> material
        for i, (t, a) in self.e.items():
            if t == "IFCRELDEFINESBYPROPERTIES":
                for r in self.refs(a[4]):
                    self.psets[r].append(self.id(a[5]))
            elif t == "IFCRELDEFINESBYTYPE":
                for r in self.refs(a[4]):
                    self.tipo_de[r] = self.id(a[5])
            elif t == "IFCRELASSOCIATESMATERIAL":
                for r in self.refs(a[4]):
                    self.material_de[r] = self.id(a[5])
            elif t.endswith("TYPE") and len(a) > 5 and isinstance(a[5], list):   # HasPropertySets de un tipo
                for r in self.refs(a[5]):
                    self.psets[i].append(r)
        self.escala_longitud = self._escala_longitud()

    @staticmethod
    def id(v):
        return v[1] if isinstance(v, tuple) else None

    def refs(self, lista):
        return [x[1] for x in (lista or []) if isinstance(x, tuple)]

    def nombre(self, i):
        t, a = self.e.get(i, ("", []))
        return a[2] if len(a) > 2 and isinstance(a[2], str) else ""

    def _escala_longitud(self):
        for t, a in self.e.values():
            if t == "IFCSIUNIT" and len(a) > 3 and a[1] == "LENGTHUNIT":
                return {"MILLI": 0.001, "CENTI": 0.01, None: 1.0}.get(a[2], 1.0)
        return 1.0

    def propiedades(self, obj):
        """{(pset, propiedad): (valor, #id_propiedad, #id_dueño)} del objeto y de su tipo (el del objeto gana)."""
        salida = {}
        for fuente in [self.tipo_de.get(obj), obj]:
            if fuente is None:
                continue
            for ps in self.psets.get(fuente, []):
                t, a = self.e.get(ps, ("", []))
                if t == "IFCPROPERTYSET":
                    for p in self.refs(a[4]):
                        tp, ap = self.e.get(p, ("", []))
                        if tp == "IFCPROPERTYSINGLEVALUE" and len(ap) > 2:
                            v = ap[2]
                            salida[(a[2], ap[0])] = ((v[1] if isinstance(v, list) and len(v) > 1 else v), p, fuente)
                elif t == "IFCELEMENTQUANTITY":
                    for q in self.refs(a[5]):
                        tq, aq = self.e.get(q, ("", []))
                        if tq.startswith("IFCQUANTITY") and len(aq) > 3:
                            salida[(a[2], aq[0])] = (aq[3], q, fuente)
        return salida

    def cantidad(self, props, nombre):
        for (ps, n), (v, _, _) in props.items():
            if n == nombre and isinstance(v, float):
                return v
        return None

    def materiales(self, obj):
        """Nombre del material y capas (material, espesor m) si las hay; mira la ocurrencia y su tipo."""
        for fuente in [obj, self.tipo_de.get(obj)]:
            m = self.material_de.get(fuente)
            if m is None:
                continue
            t, a = self.e.get(m, ("", []))
            if t == "IFCMATERIALLAYERSETUSAGE":
                m = self.id(a[0]); t, a = self.e.get(m, ("", []))
            if t == "IFCMATERIALLAYERSET":
                capas = []
                for c in self.refs(a[0]):
                    tc, ac = self.e[c]
                    mat = self.e.get(self.id(ac[0]), ("", [""]))[1]
                    capas.append({"material": mat[0] if mat else "", "espesor_m": round(ac[1] * self.escala_longitud, 4) if isinstance(ac[1], float) else None})
                return {"nombre": a[1] if len(a) > 1 else "", "capas": capas, "fuente": f"#{m}"}
            if t == "IFCMATERIAL":
                return {"nombre": a[0], "capas": [], "fuente": f"#{m}"}
            if t == "IFCMATERIALCONSTITUENTSET":
                nombres = [self.e[self.id(self.e[c][1][2])][1][0] for c in self.refs(a[2]) if self.id(self.e[c][1][2]) in self.e]
                return {"nombre": a[0] or ", ".join(nombres), "capas": [], "fuente": f"#{m}", "componentes": nombres}
            if t == "IFCMATERIALLIST":
                return {"nombre": ", ".join(self.e[r][1][0] for r in self.refs(a[0])), "capas": [], "fuente": f"#{m}"}
        return {"nombre": "", "capas": [], "fuente": ""}

def grados(dms):
    """IfcCompoundPlaneAngleMeasure (grados, minutos, segundos, millonésimas) → grados decimales."""
    if not dms:
        return None
    g, m, s = (list(dms) + [0, 0, 0])[:3]
    micro = dms[3] if len(dms) > 3 else 0
    signo = -1 if any(x < 0 for x in [g, m, s, micro]) else 1
    return round(signo * (abs(g) + abs(m) / 60 + (abs(s) + abs(micro) / 1e6) / 3600), 6)

# ---------- extracción ----------
TERMICAS = {"thermaltransmittance": "U", "heat transfer coefficient (u)": "U", "solar heat gain coefficient": "SHGC",
            "solarheatgaintransmittance": "SHGC", "g-value": "SHGC", "absorptance": "absortancia",
            "thermal resistance (r)": "R", "visual light transmittance": "transmitancia visible"}
CLASES = {"IFCWALL": "muro", "IFCWALLSTANDARDCASE": "muro", "IFCWINDOW": "ventana", "IFCSLAB": "losa",
          "IFCROOF": "techo", "IFCDOOR": "puerta", "IFCPLATE": "panel", "IFCCURTAINWALL": "muro cortina",
          "IFCGEOGRAPHICELEMENT": "terreno"}
# área de cada clase: primero la cantidad estándar IFC; si falta, el parámetro de Revit (se registra cuál)
AREAS = ["NetSideArea", "NetArea", "Area"]

def extraer(ruta):
    mo = Modelo(ruta)
    archivo = os.path.basename(ruta)
    res = {"archivo": archivo, "esquema_ifc": mo.esquema, "exportado_por": mo.origen, "escala_longitud_m": mo.escala_longitud}

    # ubicación
    sitio = next(((i, a) for i, (t, a) in mo.e.items() if t == "IFCSITE"), None)
    ubic = {"latitud": None, "longitud": None, "elevacion_m": None, "direccion": "", "por_defecto": False, "motivos": [], "fuente": ""}
    if sitio:
        i, a = sitio
        ubic.update(latitud=grados(a[9]), longitud=grados(a[10]), elevacion_m=a[11], fuente=f"{archivo} #{i} IFCSITE")
        dir_ = mo.e.get(mo.id(a[13]) if len(a) > 13 else None)
        if dir_ is None:   # Revit suele colgar la dirección del proyecto o del edificio
            dir_ = next((v for v in mo.e.values() if v[0] == "IFCPOSTALADDRESS"), None)
        if dir_:
            d = dir_[1]
            partes = [x for x in (d[4] or [])] + [d[6], d[7], d[8], d[9]]
            ubic["direccion"] = ", ".join(str(x) for x in partes if x)
        if POR_DEFECTO.search(str(a[2] or "")):
            ubic["motivos"].append(f"el emplazamiento se llama \"{a[2]}\"")
        if POR_DEFECTO.search(ubic["direccion"]):
            ubic["motivos"].append("la dirección es el texto de ejemplo del programa")
        if re.search(r"ProjectSite:[^,\]]*(por defecto|default)", mo.cabecera, re.I):
            ubic["motivos"].append("el encabezado del IFC dice que el emplazamiento es el de por defecto")
        if ubic["latitud"] is None:
            ubic["motivos"].append("el IFC no trae latitud/longitud")
        ubic["por_defecto"] = bool(ubic["motivos"])
    else:
        ubic["motivos"].append("el IFC no tiene IFCSITE")
        ubic["por_defecto"] = True
    res["ubicacion"] = ubic

    # espacios
    esp = []
    for i, (t, a) in mo.e.items():
        if t == "IFCSPACE":
            p = mo.propiedades(i)
            esp.append({"id": f"#{i}", "nombre": a[2] or "", "nombre_largo": a[7] if len(a) > 7 else "",
                        "area_neta_m2": mo.cantidad(p, "NetFloorArea"), "volumen_neto_m3": mo.cantidad(p, "NetVolume"),
                        "volumen_bruto_m3": mo.cantidad(p, "GrossVolume")})
    suma = lambda xs, k: round(sum(x[k] for x in xs if x[k] is not None), 2)
    res["espacios"] = {"n": len(esp), "area_neta_total_m2": suma(esp, "area_neta_m2"), "volumen_neto_total_m3": suma(esp, "volumen_neto_m3"),
                       "volumen_bruto_total_m3": suma(esp, "volumen_bruto_m3"), "lista": esp}

    # elementos de la envolvente
    elementos = collections.defaultdict(list)
    for i, (t, a) in mo.e.items():
        if t in CLASES:
            p = mo.propiedades(i)
            ext = next((v for (ps, n), (v, _, _) in p.items() if n == "IsExternal"), None)
            tipo = mo.tipo_de.get(i)
            area = next(((v, f"{ps}.{n}") for q in AREAS for (ps, n), (v, _, _) in p.items() if n == q and isinstance(v, float)), (None, ""))
            elementos[CLASES[t]].append({
                "id": f"#{i}", "nombre": a[2] or "", "tipo": mo.nombre(tipo) if tipo else "",
                "exterior": {"T": True, "F": False}.get(ext), "material": mo.materiales(i),
                "area_m2": area[0], "area_fuente": area[1],
                "espesor_m": (lambda w: round(w * mo.escala_longitud, 4) if w else None)(mo.cantidad(p, "Width") if t.startswith("IFCWALL") else mo.cantidad(p, "Depth")),
                "volumen_m3": mo.cantidad(p, "NetVolume")})
    res["elementos"] = {}
    for clase, xs in elementos.items():
        res["elementos"][clase] = {
            "n": len(xs), "n_exteriores": sum(1 for x in xs if x["exterior"]), "area_total_m2": suma(xs, "area_m2"),
            "area_exterior_m2": round(sum(x["area_m2"] or 0 for x in xs if x["exterior"]), 2),
            "volumen_total_m3": suma(xs, "volumen_m3"),
            "espesores_m": sorted({x["espesor_m"] for x in xs if x["espesor_m"]}),
            "materiales": dict(collections.Counter(x["material"]["nombre"] for x in xs)),
            "area_por_fuente": dict(collections.Counter(x["area_fuente"] or "sin área" for x in xs)),
            "con_capas": sum(1 for x in xs if x["material"]["capas"]), "lista": xs}

    # propiedades térmicas (de ocurrencias y de tipos), agrupadas por magnitud, clase y valor
    grupos = {}
    for i, (t, a) in mo.e.items():
        if not (t in CLASES or t.endswith("TYPE")):
            continue
        for (ps, n), (v, pid, fuente) in mo.propiedades(i).items():
            magnitud = TERMICAS.get(str(n).lower())
            if magnitud is None or not isinstance(v, float):
                continue
            ft, fa = mo.e[fuente]
            clase = CLASES.get(ft) or CLASES.get(ft[:-4], ft.lower())
            g = grupos.setdefault((magnitud, clase, round(v, 4)), {"magnitud": magnitud, "clase": clase, "valor": v, "propiedades": set(),
                                                                   "tipos": {}, "motivos": []})
            g["propiedades"].add(f"{ps}.{n}")
            if fuente not in g["tipos"]:
                ocurr = len([o for o, ti in mo.tipo_de.items() if ti == fuente]) if ft.endswith("TYPE") else 1
                g["tipos"][fuente] = (fa[2] or "", ocurr)
    termicas = []
    for g in grupos.values():
        nombres = [n for n, _ in g["tipos"].values()]
        x = {"magnitud": g["magnitud"], "clase": g["clase"], "valor": g["valor"], "propiedades": sorted(g["propiedades"]),
             "n_tipos": len(g["tipos"]), "ocurrencias": sum(o for _, o in g["tipos"].values()),
             "en": ", ".join(f"#{k} '{n}'" for k, (n, _) in list(g["tipos"].items())[:4]) + (" …" if len(g["tipos"]) > 4 else ""),
             "motivos": []}
        if any(POR_DEFECTO.search(n) for n in nombres):
            x["motivos"].append("el tipo se llama 'por defecto'/genérico")
        if x["n_tipos"] >= 3:
            x["motivos"].append(f"el mismo valor aparece en {x['n_tipos']} tipos distintos")
        termicas.append(x)
    for x in termicas:
        if x["magnitud"] == "U":
            if not 0 < x["valor"] <= 10:
                x["motivos"].append("U fuera de lo físicamente posible para un elemento (0–10 W/m²K)")
            ip = x["valor"] / BTU * 100
            if abs(ip - round(ip)) < 0.06 and round(ip) % 5 == 0:
                x["motivos"].append(f"equivale a {round(ip) / 100:.2f} Btu/h·ft²·°F, número redondo típico de los valores por defecto de Revit")
        if x["magnitud"] in ("SHGC", "absortancia", "transmitancia visible") and not 0 <= x["valor"] <= 1:
            x["motivos"].append("fracción fuera de 0–1")
        if x["magnitud"] in ("SHGC", "transmitancia visible") and x["valor"] == 0 and x["clase"] == "panel":
            x["motivos"].append("panel opaco: el valor no describe una ventana")
        x["revisar"] = True
    res["propiedades_termicas"] = termicas

    # avisos de geometría
    avisos = []
    muros = res["elementos"].get("muro")
    if muros and muros["n"] and muros["n_exteriores"] == muros["n"]:
        avisos.append(f"los {muros['n']} muros están marcados como exteriores (IsExternal): revisar medianeras y muros interiores")
    if muros and muros["n"] and not muros["con_capas"]:
        avisos.append("ningún muro tiene capas de material: el IFC no permite calcular su U")
    e = res["espacios"]
    if e["volumen_neto_total_m3"] and e["volumen_bruto_total_m3"] and e["volumen_neto_total_m3"] > e["volumen_bruto_total_m3"]:
        avisos.append("el volumen neto de los espacios es mayor que el bruto: cantidades de espacios incoherentes")
    res["avisos"] = avisos
    return res

# ---------- salidas ----------
def candidatos(res):
    """Filas de trazabilidad para el escenario base (escenario_id = base), siempre con estado = revisar."""
    arch, filas = res["archivo"], []
    mapa = {("U", "ventana"): ("U_ventana", "W/m²K"), ("SHGC", "ventana"): ("SHGC_ventana", ""),
            ("U", "muro"): ("U_muro_ext", "W/m²K"), ("absortancia", "muro"): ("absortancia_muro", ""),
            ("U", "techo"): ("U_techo", "W/m²K"), ("absortancia", "techo"): ("absortancia_techo", "")}
    por_campo = collections.defaultdict(list)
    for x in res["propiedades_termicas"]:
        if (x["magnitud"], x["clase"]) in mapa:
            por_campo[mapa[(x["magnitud"], x["clase"])]].append(x)
    for (campo, unidad), xs in por_campo.items():
        valores = sorted({round(x["valor"], 4) for x in xs})
        motivos = sorted({m for x in xs for m in x["motivos"]})
        filas.append({"escenario_id": "base", "campo": campo, "valor": valores[0] if len(valores) == 1 else "",
                      "unidad": unidad, "origen": "ifc", "fuente": f"{arch}: " + "; ".join(f"{x['en']} {'/'.join(x['propiedades'])}={x['valor']:g}" for x in xs),
                      "estado": "revisar", "nota": ("varios valores: " + ", ".join(map(str, valores)) + ". " if len(valores) > 1 else "") + "; ".join(motivos)})
    u = res["ubicacion"]
    if u["latitud"] is not None:
        filas.append({"escenario_id": "", "campo": "ubicacion_lat_lon", "valor": f"{u['latitud']}, {u['longitud']}", "unidad": "°",
                      "origen": "ifc", "fuente": u["fuente"], "estado": "revisar", "nota": "; ".join(u["motivos"]) or "confirmar que es la ubicación real"})
    return filas

def informe(res):
    u, e = res["ubicacion"], res["espacios"]
    l = [f"# Hallazgos del IFC — {res['archivo']}", "", f"Esquema {res['esquema_ifc']}. Exportado por: {res['exportado_por'][:160]}", "",
         "## Ubicación", ""]
    if u["por_defecto"]:
        l.append(f"**No usar.** Lat {u['latitud']}, lon {u['longitud']} ({u['direccion'] or 'sin dirección'}). Motivos: {'; '.join(u['motivos'])}. "
                 "Hay que dar la ubicación real (dirección, municipio o coordenadas).")
    else:
        l.append(f"Lat {u['latitud']}, lon {u['longitud']}, elevación {u['elevacion_m']} m. {u['direccion']}. Confirmar con la persona usuaria.")
    l += ["", "## Geometría (sirve para el simulador)", "",
          f"- Espacios: {e['n']}, área neta {e['area_neta_total_m2']} m², volumen neto {e['volumen_neto_total_m3']} m³."]
    for clase, x in res["elementos"].items():
        l.append(f"- {clase.capitalize()}: {x['n']} ({x['n_exteriores']} marcados exteriores), área {x['area_total_m2']} m² "
                 f"(exterior {x['area_exterior_m2']} m²; área tomada de {x['area_por_fuente']}), espesores {x['espesores_m'] or '—'} m, "
                 f"materiales {x['materiales']}, con capas: {x['con_capas']}.")
    l += ["", "## Propiedades térmicas (todas en *revisar*)", "", "| Magnitud | Valor | Tipos (ocurrencias) | Dónde | Motivos para dudar |", "|---|---|---|---|---|"]
    for x in sorted(res["propiedades_termicas"], key=lambda x: (x["clase"], x["magnitud"])):
        l.append(f"| {x['magnitud']} ({x['clase']}) | {x['valor']:g} | {x['n_tipos']} ({x['ocurrencias']}) | {x['en']} | "
                 f"{'; '.join(x['motivos']) or 'ninguno detectado: confirmar con ficha técnica'} |")
    l += ["", "## Avisos", ""] + [f"- {a}" for a in res["avisos"] or ["Ninguno"]]
    return "\n".join(l) + "\n"

def main():
    ap = argparse.ArgumentParser(description="Extrae del IFC lo que sirve para el esquema de confort, sin dar nada por confirmado.")
    ap.add_argument("ifc"); ap.add_argument("--salida")
    a = ap.parse_args()
    salida = a.salida or os.path.dirname(os.path.abspath(a.ifc))
    os.makedirs(salida, exist_ok=True)
    res = extraer(a.ifc)
    with open(os.path.join(salida, "ifc_resumen.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    with open(os.path.join(salida, "ifc_hallazgos.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(informe(res))
    with open(os.path.join(salida, "trazabilidad_ifc.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, TRAZA, lineterminator="\n"); w.writeheader(); w.writerows(candidatos(res))
    u = res["ubicacion"]
    print(f"OK: {res['archivo']} → {salida}")
    print(f"  ubicación: {u['latitud']}, {u['longitud']}" + (f"  ⚠ NO USAR ({'; '.join(u['motivos'])})" if u["por_defecto"] else ""))
    print(f"  propiedades térmicas: {len(res['propiedades_termicas'])}, con motivos para dudar: {sum(1 for x in res['propiedades_termicas'] if x['motivos'])}")
    for x in res["avisos"]:
        print("  aviso:", x)

if __name__ == "__main__":
    main()
