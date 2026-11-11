#!/usr/bin/env python3
"""
generar_csv_confort.py — Esquema de datos de confort térmico (v10: 27 columnas, solo variables que influyen)
Genera el CSV único para el dashboard a partir de archivos dados. No inventa
valores: lo que no está en las entradas queda vacío y se anota en el log.
La vivienda es una sola zona (sin habitaciones) y el confort siempre se mide con
ASHRAE 55 adaptativo. La temperatura operativa NO se calcula aquí ni se reduce a
máximos/mínimos: la entrega un simulador (alimentado con los parámetros de cada
escenario) como un valor por mes. Solo la temperatura exterior se reporta con
máximo y mínimo. Una fila por escenario × periodo.

Entradas
  --escenarios  CSV: escenario_id, escenario_nombre, es_base, archivo_resultados,
                [U_muro_ext, U_techo, U_ventana, SHGC_ventana, absortancia_muro,
                 absortancia_techo, ventilacion_ach, vel_aire_m_s]
  --config      CSV clave,valor: vivienda_id, aceptabilidad_pct (80|90),
                [factor_emision_kgCO2e_kWh, energia_tipo (electrica|termica),
                 COP_enfriamiento, eficiencia_calefaccion]
  --epw         archivo de clima horario, o bien
  --clima       CSV mensual: mes, T_ext_max_C, T_ext_min_C, T_ext_media_C
                (fila 'anual' opcional)
  Resultados del simulador por escenario (archivo_resultados): una fila por mes
                (mes = 1–12 o ene–dic) y, opcional, una fila mes = anual, con la
                temperatura operativa del PUNTO CENTRAL de la vivienda:
                T_operativa_C. Opcionales: [energia_enfriamiento_kWh,
                energia_calefaccion_kWh]. Otras columnas (p. ej. HR_pct) se ignoran:
                la humedad no entra en ASHRAE 55 adaptativo.
Salidas
  --salida CSV final y <salida>_log.md con faltantes, supuestos y avisos.
"""
import argparse, os, sys
import numpy as np
import pandas as pd

# la consola o un archivo redirigido en Windows puede no admitir todos los caracteres
sys.stdout.reconfigure(errors="backslashreplace")

PARAMS = ["U_muro_ext", "U_techo", "U_ventana", "SHGC_ventana", "absortancia_muro",
          "absortancia_techo", "ventilacion_ach", "vel_aire_m_s"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
COLUMNAS = (
    ["vivienda_id", "escenario_id", "escenario_nombre", "es_base"] + PARAMS +
    ["periodo", "mes",
     "T_ext_max_C", "T_ext_min_C", "T_ext_media_C",
     "T_operativa_C",
     "limite_sup_C", "limite_inf_C", "exceso_sobre_limite_C", "deficit_bajo_limite_C",
     "energia_total_kWh", "carbono_kgCO2e",
     "delta_fuera_rango_C", "delta_energia_pct",
     "aceptabilidad_pct"])

LOG = {"faltantes": [], "supuestos": [], "avisos": []}
def log(tipo, msg):
    if msg not in LOG[tipo]:
        LOG[tipo].append(msg)

def num(x):
    try:
        if x is None or (isinstance(x, str) and x.strip().upper() in ("", "ND", "NA", "N/A")):
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan

def mes_num(x):
    """1–12 a partir de '1'…'12' o 'ene'…'dic'; 'anual' se conserva; otro valor → None."""
    s = str(x).strip().lower()
    if s == "anual":
        return "anual"
    if s[:3] in MESES:
        return MESES.index(s[:3]) + 1
    n = num(s)
    return int(n) if not np.isnan(n) and 1 <= n <= 12 else None

def leer_config(path):
    df = pd.read_csv(path, dtype=str).fillna("")
    cfg = {r["clave"].strip(): r["valor"].strip() for _, r in df.iterrows()}
    for k in ["vivienda_id", "aceptabilidad_pct"]:
        if not cfg.get(k):
            log("faltantes", f"config: falta '{k}'")
    return cfg

def leer_epw(path):
    rows = pd.read_csv(path, skiprows=8, header=None)
    yr = 2001  # año ficticio no bisiesto solo para indexar; el EPW es un año típico
    fh = pd.to_datetime(dict(year=yr, month=rows[1], day=rows[2], hour=rows[3] - 1))
    return pd.DataFrame({"fecha_hora": fh, "T_exterior_C": rows[6].astype(float)})

def leer_clima(a):
    """Clima por periodo (índice 1–12 y 'anual'): T_ext_max_C, T_ext_min_C, T_ext_media_C."""
    cols = ["T_ext_max_C", "T_ext_min_C", "T_ext_media_C"]
    if a.epw:
        e = leer_epw(a.epw)
        g = e.groupby(e["fecha_hora"].dt.month)["T_exterior_C"]
        c = pd.DataFrame({"T_ext_max_C": g.max(), "T_ext_min_C": g.min(), "T_ext_media_C": g.mean()})
        c.loc["anual"] = [e["T_exterior_C"].max(), e["T_exterior_C"].min(), e["T_exterior_C"].mean()]
        return c
    if not a.clima:
        sys.exit("Sin --epw ni --clima: no se puede aplicar ASHRAE 55 adaptativo")
    c = pd.read_csv(a.clima, dtype={"mes": str})
    c.index = c["mes"].map(mes_num)
    c = c[c.index.notna()].reindex(columns=cols).astype(float)
    for k in cols:
        if c[k].isna().all():
            log("faltantes", f"clima: falta '{k}'")
    faltan = [MESES[m - 1] for m in range(1, 13) if m not in c.index]
    if faltan:
        log("faltantes", f"clima: sin datos para {', '.join(faltan)}")
    if "anual" not in c.index:
        m = c.drop(index="anual", errors="ignore").reindex(range(1, 13))
        media = np.nan if m["T_ext_media_C"].isna().any() else float(np.average(m["T_ext_media_C"], weights=DIAS_MES))
        c.loc["anual"] = [m["T_ext_max_C"].max(), m["T_ext_min_C"].min(), media]
        log("supuestos", "clima anual: máx/mín de los meses y media ponderada por días de cada mes")
    return c

def extra_vel(v):
    """Aumento del límite superior adaptativo por velocidad del aire (ASHRAE 55, escalones)."""
    return np.where(np.isnan(v), 0.0, np.where(v >= 1.2, 2.2, np.where(v >= 0.9, 1.8, np.where(v >= 0.6, 1.2, 0.0))))

def limites(tpma, t_op, v, acept):
    """Límites ASHRAE 55 adaptativos (inf, sup); NaN si falta un dato o tpma sale de 10–33.5 °C."""
    if np.isnan(acept) or np.isnan(tpma) or not 10 <= tpma <= 33.5:
        return np.nan, np.nan
    banda = 2.5 if acept == 90 else 3.5
    t_conf = 0.31 * tpma + 17.8
    return t_conf - banda, t_conf + banda + (float(extra_vel(np.float64(v))) if t_op > 25 else 0.0)

def energia_total(df, cfg):
    """Energía total (kWh) por fila; convierte carga térmica solo con COP dado. None si no se puede."""
    enf = df["energia_enfriamiento_kWh"].astype(float) if "energia_enfriamiento_kWh" in df else None
    cal = df["energia_calefaccion_kWh"].astype(float) if "energia_calefaccion_kWh" in df else None
    if enf is None and cal is None:
        log("faltantes", "los resultados no traen energía: columnas de energía y carbono vacías")
        return None
    tipo = cfg.get("energia_tipo", "").lower()
    if tipo == "termica":
        cop, efi = num(cfg.get("COP_enfriamiento")), num(cfg.get("eficiencia_calefaccion"))
        if (enf is not None and np.isnan(cop)) or (cal is not None and np.isnan(efi)):
            log("faltantes", "energía térmica sin COP/eficiencia: no se convierte a energía eléctrica (queda vacía)")
            return None
        enf = enf / cop if enf is not None else 0
        cal = cal / efi if cal is not None else 0
    elif tipo != "electrica":
        log("avisos", "config sin energia_tipo: se usa la energía tal como la entrega el simulador")
    return (enf if enf is not None else 0) + (cal if cal is not None else 0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escenarios", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--epw"); ap.add_argument("--clima")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    base_dir = os.path.dirname(os.path.abspath(a.escenarios))
    cfg = leer_config(a.config)
    esc = pd.read_csv(a.escenarios, dtype=str).fillna("")
    for p in PARAMS:
        if p not in esc or (esc[p] == "").all():
            log("faltantes", f"escenarios: parámetro '{p}' sin valor en ningún escenario")
    if (esc["es_base"].str.lower().isin(["si", "sí", "1"])).sum() != 1:
        log("avisos", "debe haber exactamente un escenario con es_base = Si; deltas vacíos si no")
    factor = num(cfg.get("factor_emision_kgCO2e_kWh"))
    if np.isnan(factor):
        log("faltantes", "factor_emision_kgCO2e_kWh no dado: carbono vacío")
    acept = num(cfg.get("aceptabilidad_pct"))
    if np.isnan(acept):
        log("faltantes", "aceptabilidad_pct no dada: no se calculan límites de confort")

    clima = leer_clima(a)
    log("supuestos", "media exterior predominante = media exterior mensual (tope de 30 días de ASHRAE 55), "
                     "porque el simulador entrega un valor de T_operativa por mes")
    tm = clima.loc[[m for m in range(1, 13) if m in clima.index], "T_ext_media_C"].dropna()
    fuera = [MESES[m - 1] for m, t in tm.items() if not 10 <= t <= 33.5]
    if fuera:
        log("avisos", f"media exterior fuera de 10–33.5 °C en {', '.join(fuera)}: fuera del alcance del método adaptativo, sin límites ni exceso/déficit")
    if tm.empty:
        log("faltantes", "sin T_ext_media_C mensual: no se identifican mes caliente ni mes frío")
    clave = [("anual", "anual")] + ([("mes_caliente", int(tm.idxmax())), ("mes_frio", int(tm.idxmin()))] if len(tm) else [])

    filas = []
    for _, s in esc.iterrows():
        arch = s.get("archivo_resultados", "")
        ruta = arch if os.path.isabs(arch) else os.path.join(base_dir, arch)
        if not arch or not os.path.exists(ruta):
            log("faltantes", f"{s['escenario_id']}: no existe archivo_resultados '{arch}' — escenario sin resultados")
            continue
        res = pd.read_csv(ruta, dtype={"mes": str})
        res.index = res["mes"].map(mes_num)
        if res.index.isna().any():
            log("avisos", f"{s['escenario_id']}: filas con 'mes' no reconocido (se ignoran)")
            res = res[res.index.notna()]
        if res.index.duplicated().any():
            log("avisos", f"{s['escenario_id']}: mes repetido en los resultados; se usa la primera fila (debe haber un solo valor por mes para toda la vivienda)")
            res = res[~res.index.duplicated()]
        if "T_operativa_C" not in res:
            log("faltantes", f"{s['escenario_id']}: los resultados no traen T_operativa_C: columna vacía")
            res["T_operativa_C"] = np.nan
        faltan = [MESES[m - 1] for m in range(1, 13) if m not in res.index]
        if faltan:
            log("faltantes", f"{s['escenario_id']}: sin resultados para {', '.join(faltan)}")
        en = energia_total(res, cfg)
        val = lambda k, c: float(res.at[k, c]) if k in res.index and pd.notna(res.at[k, c]) else np.nan
        cli = lambda k, c: float(clima.at[k, c]) if k in clima.index else np.nan
        v = num(s.get("vel_aire_m_s", ""))

        def periodo(k):
            top = val(k, "T_operativa_C")
            r = {c: cli(k, c) for c in ["T_ext_max_C", "T_ext_min_C", "T_ext_media_C"]}
            r.update(T_operativa_C=top,
                     energia_total_kWh=float(en[k]) if en is not None and k in en.index and pd.notna(en[k]) else np.nan)
            if k != "anual":
                li, ls = limites(r["T_ext_media_C"], top, v, acept)
                r.update(limite_inf_C=li, limite_sup_C=ls,
                         exceso_sobre_limite_C=np.clip(top - ls, 0, None), deficit_bajo_limite_C=np.clip(li - top, 0, None))
            return r

        mensual = {m: periodo(m) for m in range(1, 13)}
        anual = periodo("anual")
        if np.isnan(anual["T_operativa_C"]):
            log("faltantes", f"{s['escenario_id']}: el simulador no da T_operativa anual: queda vacía (no se promedian meses)")
        e_mes = [mensual[m]["energia_total_kWh"] for m in range(1, 13)]
        if not np.isnan(e_mes).any():
            anual["energia_total_kWh"] = sum(e_mes)
        # año: sin límite propio (cada mes tiene el suyo); exceso/déficit = el del peor mes,
        # vacío si falta la T_op de algún mes (el peor podría ser justo ese)
        completo = not any(np.isnan(mensual[m]["T_operativa_C"]) for m in range(1, 13))
        if not completo:
            log("faltantes", f"{s['escenario_id']}: falta la T_operativa de algún mes: exceso/déficit y energía anuales vacíos")
        for c in ["exceso_sobre_limite_C", "deficit_bajo_limite_C"]:
            xs = [mensual[m][c] for m in range(1, 13) if not np.isnan(mensual[m][c])]
            anual[c] = max(xs) if xs and completo else np.nan
        comunes = {"vivienda_id": cfg.get("vivienda_id", ""), "escenario_id": s["escenario_id"],
                   "escenario_nombre": s["escenario_nombre"], "es_base": s["es_base"],
                   **{p: num(s.get(p, "")) for p in PARAMS}, "aceptabilidad_pct": acept}
        periodos = [(per, anual if k == "anual" else mensual[k], "" if k == "anual" else k) for per, k in clave] + \
                   [(MESES[m - 1], mensual[m], m) for m in range(1, 13)]
        for per, r, mes in periodos:
            filas.append({**r, **comunes, "periodo": per, "mes": mes,
                          "carbono_kgCO2e": r["energia_total_kWh"] * factor})
    if not filas:
        escribir_log(a.salida, 0, 0)
        sys.exit(f"Sin filas generadas: faltan los resultados del simulador (archivo_resultados). Detalle en {os.path.splitext(a.salida)[0]}_log.md")
    df = pd.DataFrame(filas).reindex(columns=COLUMNAS)
    # deltas contra base (mismo periodo). Grados fuera del rango = exceso + déficit:
    # negativo = el escenario queda más cerca del rango que el base
    fuera = df["exceso_sobre_limite_C"] + df["deficit_bajo_limite_C"]
    b = df.assign(fuera=fuera)[df["es_base"].str.lower().isin(["si", "sí", "1"])].set_index("periodo")
    if len(b):
        k = list(df["periodo"])
        g = lambda c: np.array([b[c].get(i, np.nan) for i in k], dtype=float)
        df["delta_fuera_rango_C"] = fuera - g("fuera")
        with np.errstate(divide="ignore", invalid="ignore"):
            be = g("energia_total_kWh")
            df["delta_energia_pct"] = np.where(be > 0, 100 * (df["energia_total_kWh"] - be) / be, np.nan)
    num_cols = df.select_dtypes("number").columns
    df[num_cols] = df[num_cols].round(2)
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")
    df.to_csv(a.salida, index=False, encoding="utf-8")
    escribir_log(a.salida, len(df), df["escenario_id"].nunique())
    print(f"OK: {len(df)} filas → {a.salida}")

def escribir_log(salida, n_filas, n_escenarios):
    with open(os.path.splitext(salida)[0] + "_log.md", "w", encoding="utf-8") as f:
        f.write(f"# Log de generación — {os.path.basename(salida)}\n\n")
        f.write(f"Filas: {n_filas} · Escenarios: {n_escenarios}\n\n")
        for t, titulo in [("faltantes", "Datos faltantes (celdas vacías)"), ("supuestos", "Supuestos de método aplicados"), ("avisos", "Avisos")]:
            f.write(f"## {titulo}\n\n" + ("\n".join(f"- {m}" for m in LOG[t]) or "- Ninguno") + "\n\n")

if __name__ == "__main__":
    main()
