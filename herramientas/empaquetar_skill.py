#!/usr/bin/env python3
"""
empaquetar_skill.py — Sincroniza y empaqueta las skills del proyecto.

1. Copia las fuentes de verdad a cada skill:
     esquema-confort-termico:
       backend/generar_csv_confort.py, backend/importacion/*.py -> scripts/
       backend/importacion/plantillas/                          -> plantillas/
       docs/contexto_esquema_confort.md, docs/metodologia_calculo.md
     instalar-proyecto:
       instalar.py                                              -> scripts/
2. Crea dist/<skill>.skill (zip) de cada una, para instalarlas en Claude (Cowork, claude.ai o Code).

Uso: python herramientas/empaquetar_skill.py
"""
import glob, os, shutil, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(RAIZ, ".claude", "skills")
IMPORTACION = os.path.join(RAIZ, "backend", "importacion")

def copiar(archivos, destino):
    os.makedirs(destino, exist_ok=True)
    for a in archivos:
        shutil.copy2(a, destino)

esquema = os.path.join(SKILLS, "esquema-confort-termico")
copiar([os.path.join(RAIZ, "backend", "generar_csv_confort.py")] + sorted(glob.glob(os.path.join(IMPORTACION, "*.py"))), os.path.join(esquema, "scripts"))
shutil.copytree(os.path.join(IMPORTACION, "plantillas"), os.path.join(esquema, "plantillas"), dirs_exist_ok=True)
copiar([os.path.join(RAIZ, "docs", d) for d in ["contexto_esquema_confort.md", "metodologia_calculo.md"]], esquema)

instalar = os.path.join(SKILLS, "instalar-proyecto")
copiar([os.path.join(RAIZ, "instalar.py")], os.path.join(instalar, "scripts"))

os.makedirs(os.path.join(RAIZ, "dist"), exist_ok=True)
for skill in [esquema, instalar]:
    nombre = os.path.basename(skill)
    salida = os.path.join(RAIZ, "dist", f"{nombre}.skill")
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for carpeta, dirs, archivos in sorted(os.walk(skill)):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for a in sorted(archivos):
                ruta = os.path.join(carpeta, a)
                z.write(ruta, os.path.relpath(ruta, SKILLS))
    print(f"Skill {nombre} sincronizada y empaquetada en {os.path.relpath(salida, RAIZ)}")
