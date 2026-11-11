#!/usr/bin/env python3
"""
armar_entradas.py — Convierte la trazabilidad en las entradas de generar_csv_confort.py.

Solo pasa los valores con estado = confirmado. Lo que está en "revisar" o "faltante" queda
vacío en las entradas y aparece en pendientes.md con su nota. Nunca completa un dato por su cuenta.

trazabilidad.csv (una o varias, se leen en orden): escenario_id, campo, valor, unidad, origen, fuente, estado, nota
  escenario_id vacío   → dato de la vivienda (config.csv): vivienda_id, aceptabilidad_pct, factor_emision_kgCO2e_kWh,
                          energia_tipo, COP_enfriamiento, eficiencia_calefaccion
  escenario_id = base  → el escenario que tenga es_base = Si
  escenario_id = ESC-… → escenario_nombre, es_base y los 8 parámetros; valor "=base" copia el del escenario base
                          (solo si en ese escenario la medida no cambia, y la persona usuaria lo confirmó)

Uso:  python armar_entradas.py trazabilidad.csv [otra.csv …] --salida entradas/
Escribe: escenarios.csv, config.csv, resultados_PLANTILLA.csv (formato que debe llenar el simulador) y pendientes.md.
"""
import argparse, csv, os, sys

sys.stdout.reconfigure(errors="backslashreplace")
PARAMS = ["U_muro_ext", "U_techo", "U_ventana", "SHGC_ventana", "absortancia_muro", "absortancia_techo", "ventilacion_ach", "vel_aire_m_s"]
CONFIG = ["vivienda_id", "aceptabilidad_pct", "factor_emision_kgCO2e_kWh", "energia_tipo", "COP_enfriamiento", "eficiencia_calefaccion"]
RESULTADOS = ["mes", "T_operativa_C", "energia_enfriamiento_kWh", "energia_calefaccion_kWh"]
# valores admitidos (docs/diccionario de variables); fuera de rango → no se usa y se reporta
RANGOS = {"U_muro_ext": (0, 10), "U_techo": (0, 10), "U_ventana": (0, 10), "SHGC_ventana": (0, 1), "absortancia_muro": (0, 1),
          "absortancia_techo": (0, 1), "ventilacion_ach": (0, 100), "vel_aire_m_s": (0, 5), "factor_emision_kgCO2e_kWh": (0, 5),
          "COP_enfriamiento": (0, 20), "eficiencia_calefaccion": (0, 10)}
OPCIONES = {"aceptabilidad_pct": {"80", "90"}, "energia_tipo": {"electrica", "termica"}, "es_base": {"Si", "No"}}

def valido(campo, valor):
    if campo in OPCIONES:
        return valor in OPCIONES[campo]
    if campo in RANGOS:
        try:
            v = float(str(valor).replace(",", "."))
        except ValueError:
            return False
        lo, hi = RANGOS[campo]
        return lo <= v <= hi and not (campo.startswith(("U_", "COP", "eficiencia")) and v == 0)
    return bool(str(valor).strip())

def main():
    ap = argparse.ArgumentParser(description="Entradas del esquema a partir de la trazabilidad (solo datos confirmados).")
    ap.add_argument("trazas", nargs="+"); ap.add_argument("--salida", default="entradas")
    a = ap.parse_args()
    filas = []
    for t in a.trazas:
        with open(t, encoding="utf-8-sig", newline="") as f:
            filas += [dict(r, archivo=os.path.basename(t)) for r in csv.DictReader(f)]
    datos, dudas, conflictos = {}, [], []
    for r in filas:
        clave = ((r.get("escenario_id") or "").strip(), (r.get("campo") or "").strip())
        valor, estado = (r.get("valor") or "").strip(), (r.get("estado") or "").strip().lower()
        if estado == "confirmado" and valor:
            if not (valor == "=base" or valido(clave[1], valor)):
                dudas.append((clave, f"valor fuera de lo admitido: {valor}", r)); continue
            if clave in datos and datos[clave][0] != valor:
                conflictos.append((clave, datos[clave][0], valor))
            datos[clave] = (valor, r)
        else:
            dudas.append((clave, estado or "sin estado", r))
    if conflictos:
        for (e, c), v1, v2 in conflictos:
            print(f"Conflicto en {e or 'vivienda'}/{c}: '{v1}' contra '{v2}', ambos confirmados.")
        sys.exit("Resuelve los conflictos en la trazabilidad antes de armar las entradas.")

    ids = sorted({e for e, _ in datos if e not in ("", "base")} | {e for (e, _), _, _ in dudas if e not in ("", "base")})
    bases = [e for e in ids if datos.get((e, "es_base"), ("",))[0] == "Si"]
    if len(bases) != 1:
        print(f"Aviso: debe haber exactamente un escenario con es_base = Si confirmado (hay {len(bases)}).")
    base = bases[0] if len(bases) == 1 else None
    if base:   # filas "base" → el id real del base, sin pisar lo confirmado para ese id
        for (e, c), v in list(datos.items()):
            if e == "base":
                datos.setdefault((base, c), v)
    # una duda deja de serlo si otra fila confirmó ese mismo dato
    dudas = [(k, m, r) for k, m, r in dudas if (base if k[0] == "base" else k[0], k[1]) not in datos]
    if datos.get(("", "energia_tipo"), ("",))[0] == "electrica":   # COP y eficiencia solo aplican a energía térmica
        dudas = [(k, m, r) for k, m, r in dudas if k[1] not in ("COP_enfriamiento", "eficiencia_calefaccion")]
    os.makedirs(a.salida, exist_ok=True)
    pendientes = []
    with open(os.path.join(a.salida, "escenarios.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["escenario_id", "escenario_nombre", "es_base", "archivo_resultados"] + PARAMS)
        for e in ids:
            fila = [e, datos.get((e, "escenario_nombre"), ("",))[0], datos.get((e, "es_base"), ("",))[0], f"resultados_{e}.csv"]
            for p in PARAMS:
                v = datos.get((e, p), ("",))[0]
                if v == "=base":
                    v = datos.get((base, p), ("",))[0] if base else ""
                if not v:
                    pendientes.append(f"{e}: {p}")
                fila.append(v)
            if not fila[1]:
                pendientes.append(f"{e}: escenario_nombre")
            w.writerow(fila)
    with open(os.path.join(a.salida, "config.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["clave", "valor"])
        for c in CONFIG:
            v = datos.get(("", c), ("",))[0]
            if v:
                w.writerow([c, v])
            elif c not in ("COP_enfriamiento", "eficiencia_calefaccion") or datos.get(("", "energia_tipo"), ("",))[0] == "termica":
                pendientes.append(f"vivienda: {c}")
    with open(os.path.join(a.salida, "resultados_PLANTILLA.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(RESULTADOS)
        w.writerows([[m] + [""] * (len(RESULTADOS) - 1) for m in list(range(1, 13)) + ["anual"]])
    faltan_res = [e for e in ids if not os.path.exists(os.path.join(a.salida, f"resultados_{e}.csv"))]
    with open(os.path.join(a.salida, "pendientes.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Pendientes para completar el esquema\n\n## Datos sin confirmar (quedaron vacíos)\n\n")
        notas = {}
        for (e, c), motivo, r in dudas:
            notas.setdefault(f"{e or 'vivienda'}: {c}", []).append(f"{motivo} — {r.get('origen', '')}: {(r.get('nota') or '')[:200]}")
        f.write("\n".join(f"- **{k}** — " + " | ".join(v) for k, v in notas.items()) or "- Ninguno")
        f.write("\n\n## Campos vacíos en las entradas\n\n" + ("\n".join(f"- {p}" for p in pendientes) or "- Ninguno"))
        f.write("\n\n## Resultados del simulador\n\nNo se generan aquí: la temperatura operativa y la energía solo salen del simulador. "
                "Falta un archivo con el formato de resultados_PLANTILLA.csv para: " + (", ".join(f"resultados_{e}.csv" for e in faltan_res) or "ninguno") + "\n")
    print(f"OK: {len(ids)} escenario(s) → {a.salida}  (base: {base or 'sin definir'})")
    print(f"  campos vacíos: {len(pendientes)} · sin confirmar: {len(dudas)} · resultados del simulador faltantes: {len(faltan_res)}")
    print(f"  detalle en {os.path.join(a.salida, 'pendientes.md')}")

if __name__ == "__main__":
    main()
