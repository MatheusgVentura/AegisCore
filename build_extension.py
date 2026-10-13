"""
AegisCore — Script de Empacotamento da Extensão de Navegador (Manifest V3)
Gera o arquivo dist/AegisCore-Companion-Extension-v2.0.0.zip para distribuição.
"""

import os
import zipfile

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
EXTENSION_DIR = os.path.join(ROOT_DIR, "extension")
DIST_DIR = os.path.join(ROOT_DIR, "dist")
ZIP_NAME = "AegisCore-Companion-Extension-v2.0.0.zip"
TARGET_ZIP = os.path.join(DIST_DIR, ZIP_NAME)


def package_extension():
    os.makedirs(DIST_DIR, exist_ok=True)

    if not os.path.exists(EXTENSION_DIR):
        raise FileNotFoundError(f"Diretório da extensão não encontrado: {EXTENSION_DIR}")

    print(f"Empacotando extensão de {EXTENSION_DIR}...")
    with zipfile.ZipFile(TARGET_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(EXTENSION_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, EXTENSION_DIR)
                zipf.write(file_path, arcname)
                print(f"  + {arcname}")

    print(f"\n[SUCESSO] Extensão empacotada com sucesso em:\n{TARGET_ZIP}")


if __name__ == "__main__":
    package_extension()
