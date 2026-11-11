#!/usr/bin/env python3
"""Crea entradas MOCK (datos inventados, no reales) para probar generar_csv_confort.py.
Hace las veces del simulador: un modelo horario burdo que se resume a un valor por mes
(y uno anual), como lo entregaría el simulador real.
Uso: python crear_mock.py [--vivienda PUE-01] [--ajuste-clima 0]
Escribe en backend/mock/entradas/<vivienda>/ (escenarios.csv, config.csv, clima.csv, resultados_*.csv)."""
import argparse, os
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--vivienda", default="PUE-01")
ap.add_argument("--ajuste-clima", type=float, default=0.0, help="°C que se suman al clima sintético")
args = ap.parse_args()
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entradas", args.vivienda)
os.makedirs(d, exist_ok=True)
t = pd.date_range("2001-01-01", periods=8760, freq="h")
rng = np.random.default_rng(42)
doy, hr = t.day_of_year.values, t.hour.values
# clima sintético tipo Puebla (valores mensuales aproximados, inventados para el mock):
# mes más caliente mayo, más frío enero; lluvias jun-sep = menos oscilación diaria
T_MES = [13.3, 14.6, 16.8, 18.5, 19.0, 18.5, 17.6, 17.7, 17.4, 16.3, 14.8, 13.6]  # media °C
OSC_MES = [8.0, 8.5, 8.5, 8.0, 7.5, 6.0, 5.0, 5.0, 5.0, 6.0, 7.0, 7.5]          # semiamplitud diaria °C
mitad = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])       # día juliano a mitad de cada mes
mensual = lambda v: np.interp(doy, np.r_[mitad[-1] - 365, mitad, mitad[0] + 365], np.r_[v[-1], v, v[0]])
diario = np.sin((hr - 9) / 24 * 2 * np.pi)  # máx ~15 h, mín ~3 h
te = args.ajuste_clima + mensual(T_MES) + mensual(OSC_MES) * diario + rng.normal(0, 0.8, len(t))
sol = np.clip(np.sin((hr - 6) / 12 * np.pi), 0, None)

# escenario: U_muro, U_techo, U_ventana, SHGC, abs_muro, abs_techo, ach, vel_aire
ESC = [
    ("ESC-00", "Base (block, losa, vidrio sencillo)", "Si", 2.5, 3.0, 5.8, 0.85, 0.6, 0.6, 0.5, 0.1),
    ("ESC-01", "Aislamiento en techo", "No", 2.5, 0.6, 5.8, 0.85, 0.6, 0.3, 0.5, 0.1),
    ("ESC-02", "Muro aislado + techo aislado", "No", 0.8, 0.6, 5.8, 0.85, 0.6, 0.3, 0.5, 0.1),
    ("ESC-03", "Aislamiento + vidrio doble", "No", 0.8, 0.6, 2.8, 0.50, 0.4, 0.3, 0.5, 0.1),
    ("ESC-04", "Todo lo anterior + ventilación nocturna y ventilador", "No", 0.8, 0.6, 2.8, 0.50, 0.4, 0.3, 3.0, 0.9),
]
filas = []
for eid, nom, base, um, ut, uv, shgc, am, at, ach, v in ESC:
    # balance burdo inventado: interior = exterior (media 24 h) + ganancias / conductancia de la envolvente
    G = um + 1.2 * ut + 0.3 * uv + 0.35 * ach                      # conductancia relativa (ventilar acopla al exterior)
    q_sol = sol * (am * 3 + at * 4 + shgc * 6)                     # ganancia solar relativa
    te24 = pd.Series(te).rolling(24, min_periods=1).mean().values
    ta = te24 + 8 * (q_sol + 3) / (G + 4) + np.clip(0.08 * G, 0.2, 0.7) * (te - te24)
    tr = ta + 0.04 * q_sol * ut - 0.2
    # cargas ideales mock: enfría sobre 26 °C, calienta bajo 18 °C (escala ~3 MWh/año en la base)
    enf = np.clip(ta - 26, 0, None) * 0.16 * (1 + 0.1 * G)
    cal = np.clip(18 - ta, 0, None) * 0.11 * (1 + 0.1 * G)
    h = pd.DataFrame({"mes": t.month, "T_operativa_C": 0.5 * ta + 0.5 * tr,
                      "energia_enfriamiento_kWh": enf, "energia_calefaccion_kWh": cal})
    # salida tipo simulador: un valor por mes y uno anual (T_op media, energía sumada)
    agg = {"T_operativa_C": "mean", "energia_enfriamiento_kWh": "sum", "energia_calefaccion_kWh": "sum"}
    res = h.groupby("mes").agg(agg)
    res.loc["anual"] = h.agg(agg)
    arch = f"resultados_{eid}.csv"
    res.round({"T_operativa_C": 2, "energia_enfriamiento_kWh": 1, "energia_calefaccion_kWh": 1}
              ).reset_index().to_csv(os.path.join(d, arch), index=False)
    filas.append([eid, nom, base, arch, um, ut, uv, shgc, am, at, ach, v])
pd.DataFrame(filas, columns=["escenario_id", "escenario_nombre", "es_base", "archivo_resultados", "U_muro_ext", "U_techo",
    "U_ventana", "SHGC_ventana", "absortancia_muro", "absortancia_techo", "ventilacion_ach", "vel_aire_m_s"]
    ).to_csv(os.path.join(d, "escenarios.csv"), index=False)
g = pd.Series(te).groupby(t.month)
clima = pd.DataFrame({"T_ext_max_C": g.max(), "T_ext_min_C": g.min(), "T_ext_media_C": g.mean()})
clima.loc["anual"] = [te.max(), te.min(), te.mean()]
clima.round(2).rename_axis("mes").reset_index().to_csv(os.path.join(d, "clima.csv"), index=False)
open(os.path.join(d, "config.csv"), "w").write(
    f"clave,valor\nvivienda_id,{args.vivienda}\naceptabilidad_pct,80\n"
    "factor_emision_kgCO2e_kWh,0.435\nenergia_tipo,electrica\n")
print("Mock listo en", d)
