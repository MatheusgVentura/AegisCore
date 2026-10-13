"""
Utilitário para gerar os ícones da Extensão de Navegador AegisCore
a partir do ícone oficial aegiscore.ico.
"""

import os
from PIL import Image

SIZES = [16, 32, 48, 128, 256]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "extension", "icons")


def generate_icons():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ico_path = os.path.join(os.path.dirname(__file__), "aegiscore.ico")

    if not os.path.exists(ico_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {ico_path}")

    with Image.open(ico_path) as img:
        img = img.convert("RGBA")
        for size in SIZES:
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            target = os.path.join(OUTPUT_DIR, f"icon{size}.png")
            resized.save(target, format="PNG")
            print(f"Gerado: {target} ({size}x{size})")


if __name__ == "__main__":
    generate_icons()
