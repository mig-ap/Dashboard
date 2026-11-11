#!/usr/bin/env python3
"""
calcular_u.py — Valor U de un elemento a partir de sus capas (ISO 6946), sin suponer nada.

Cada capa necesita espesor y conductividad (o una resistencia térmica, p. ej. una cámara de aire),
y cada conductividad o resistencia necesita su fuente (tabla de una norma, ficha técnica del
fabricante, ensayo). Si a una capa le falta el dato o la fuente, el script no calcula: lo dice.
Los espesores pueden venir del IFC (capas de material) o de planos.

  U = 1 / (Rsi + Σ espesor/conductividad + Σ R + Rse)

Resistencias superficiales: ISO 6946:2017, tabla 7 (constantes de la norma):
  Rse = 0.04 m²K/W;  Rsi = 0.13 (flujo horizontal: muros), 0.10 (hacia arriba: techos), 0.17 (hacia abajo: pisos)
Se pueden sustituir con --rsi/--rse si se usa otra norma (p. ej. NOM-020-ENER), citándola con --fuente-r.

Entrada (CSV): capa, material, espesor_m, conductividad_W_mK, resistencia_m2K_W, fuente
Uso:  python calcular_u.py capas_muro.csv --elemento muro [--campo U_muro_ext] [--escenario ESC-00]
Salida: imprime el cálculo y agrega una fila a trazabilidad_u.csv (origen = calculado).
"""
import argparse, csv, os, sys

sys.stdout.reconfigure(errors="backslashreplace")
TRAZA = ["escenario_id", "campo", "valor", "unidad", "origen", "fuente", "estado", "nota"]
RSI = {"muro": 0.13, "techo": 0.10, "piso": 0.17}
RSE = 0.04
CAMPO = {"muro": "U_muro_ext", "techo": "U_techo"}

def num(x):
    try:
        return float(str(x).replace(",", ".")) if str(x).strip() else None
    except ValueError:
        return None

def main():
    ap = argparse.ArgumentParser(description="U de un elemento por capas (ISO 6946), cada dato con su fuente.")
    ap.add_argument("capas"); ap.add_argument("--elemento", choices=list(RSI), required=True)
    ap.add_argument("--rsi", type=float); ap.add_argument("--rse", type=float); ap.add_argument("--fuente-r")
    ap.add_argument("--campo"); ap.add_argument("--escenario", default="base"); ap.add_argument("--traza", default="trazabilidad_u.csv")
    a = ap.parse_args()
    if (a.rsi is not None or a.rse is not None) and not a.fuente_r:
        sys.exit("--rsi/--rse necesitan --fuente-r (qué norma o documento las da).")
    rsi = a.rsi if a.rsi is not None else RSI[a.elemento]
    rse = a.rse if a.rse is not None else RSE
    fuente_r = a.fuente_r or "ISO 6946:2017, tabla 7"
    with open(a.capas, encoding="utf-8-sig", newline="") as f:
        capas = list(csv.DictReader(f))
    if not capas:
        sys.exit("El archivo de capas está vacío.")
    errores, total, detalle = [], rsi + rse, []
    for i, c in enumerate(capas, 1):
        e, k, r, src = num(c.get("espesor_m")), num(c.get("conductividad_W_mK")), num(c.get("resistencia_m2K_W")), (c.get("fuente") or "").strip()
        nombre = c.get("material") or c.get("capa") or f"capa {i}"
        if r is None and (e is None or k is None or k <= 0):
            errores.append(f"{nombre}: falta espesor y conductividad (o una resistencia)")
        elif not src:
            errores.append(f"{nombre}: falta la fuente de la conductividad/resistencia")
        else:
            ri = r if r is not None else e / k
            total += ri
            detalle.append(f"{nombre}: R = {ri:.4f}" + ("" if r is not None else f" ({e} m / {k} W/mK)") + f" [{src}]")
    if errores:
        print("No se calcula U: faltan datos. No se supone ningún valor.")
        for x in errores:
            print("  -", x)
        sys.exit(1)
    u = 1 / total
    print(f"Rsi = {rsi}, Rse = {rse} [{fuente_r}]")
    for x in detalle:
        print("  " + x)
    print(f"R total = {total:.4f} m²K/W  →  U = {u:.3f} W/m²K")
    campo = a.campo or CAMPO.get(a.elemento, f"U_{a.elemento}")
    nueva = not os.path.exists(a.traza)
    with open(a.traza, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, TRAZA, lineterminator="\n")
        if nueva:
            w.writeheader()
        w.writerow({"escenario_id": a.escenario, "campo": campo, "valor": round(u, 3), "unidad": "W/m²K", "origen": "calculado",
                    "fuente": f"ISO 6946 con {os.path.basename(a.capas)}; Rsi/Rse: {fuente_r}; " + "; ".join(detalle),
                    "estado": "confirmado", "nota": f"R total {total:.4f} m²K/W"})

if __name__ == "__main__":
    main()
