#!/usr/bin/env python3
"""
empaquetar_skill.py — Sincroniza y empaqueta la skill esquema-confort-termico.

1. Copia las fuentes de verdad a la skill:
     backend/generar_csv_confort.py   -> .claude/skills/esquema-confort-termico/scripts/
     backend/importacion/*.py         -> .claude/skills/esquema-confort-termico/scripts/
     backend/importacion/plantillas/  -> .claude/skills/esquema-confort-termico/plantillas/
     docs/contexto_esquema_confort.md -> .claude/skills/esquema-confort-termico/
     docs/metodologia_calculo.md      -> .claude/skills/esquema-confort-termico/
2. Crea dist/esquema-confort-termico.skill (zip) para instalarla en Claude (Cowork, claude.ai o Code).

Uso: python herramientas/empaquetar_skill.py
"""
import glob, os, shutil, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(RAIZ, ".claude", "skills")
NOMBRE = "esquema-confort-termico"
SKILL = os.path.join(SKILLS, NOMBRE)
IMPORTACION = os.path.join(RAIZ, "backend", "importacion")

os.makedirs(os.path.join(SKILL, "scripts"), exist_ok=True)
for py in [os.path.join(RAIZ, "backend", "generar_csv_confort.py")] + sorted(glob.glob(os.path.join(IMPORTACION, "*.py"))):
    shutil.copy2(py, os.path.join(SKILL, "scripts"))
shutil.copytree(os.path.join(IMPORTACION, "plantillas"), os.path.join(SKILL, "plantillas"), dirs_exist_ok=True)
for doc in ["contexto_esquema_confort.md", "metodologia_calculo.md"]:
    shutil.copy2(os.path.join(RAIZ, "docs", doc), SKILL)

os.makedirs(os.path.join(RAIZ, "dist"), exist_ok=True)
salida = os.path.join(RAIZ, "dist", f"{NOMBRE}.skill")
with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
    for carpeta, dirs, archivos in sorted(os.walk(SKILL)):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for a in sorted(archivos):
            ruta = os.path.join(carpeta, a)
            z.write(ruta, os.path.relpath(ruta, SKILLS))
print(f"Skill sincronizada y empaquetada en {os.path.relpath(salida, RAIZ)}")
