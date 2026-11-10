"""
actas_a_pdf.py: exporta las actas de reunión de la wiki a PDF.

Lee  wiki/7.1.-Actas-de-Reunión-y-Evaluación.md  y genera en  docs/actas/:
  - Actas_Challenge3_WaterGuard.pdf   (todas las actas en un solo documento)
  - Acta_1.pdf, Acta_2.pdf, Acta_3.pdf (una por reunión)

Cómo funciona: convierte el Markdown a HTML con la librería `markdown`
(tablas incluidas), le aplica una hoja de estilos para impresión y usa
Chrome o Edge en modo headless (--print-to-pdf) para generar el PDF.

Requisitos:
  pip install markdown
  Google Chrome o Microsoft Edge instalado (o la ruta en la variable CHROME_PATH)

Uso (desde la raíz del repositorio):
  python codigo/scripts/actas_a_pdf.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "wiki" / "7.1.-Actas-de-Reunión-y-Evaluación.md"
DESTINO = RAIZ / "docs" / "actas"
WIKI_URL = "https://github.com/Juan100205/IOTPROYECTOFINAL3CORTE/wiki/"

ENCABEZADO = (
    "Universidad de La Sabana · Facultad de Ingeniería · Internet de las Cosas 2026-2"
    "<br>WaterGuard v9 · Challenge #3 · Juan José Riaño Zabaleta · Santiago Peña Beltrán"
)

CSS = """
@page { size: Letter; margin: 18mm 16mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; line-height: 1.4; }
.encabezado { font-size: 8.5pt; color: #555; border-bottom: 1px solid #999; padding-bottom: 6px; margin-bottom: 14px; }
h1 { font-size: 17pt; margin: 0 0 10px; }
h2 { font-size: 14pt; margin: 18px 0 8px; border-bottom: 2px solid #1f5f8b; padding-bottom: 3px; }
h3 { font-size: 11.5pt; margin: 14px 0 6px; color: #1f5f8b; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #b5b5b5; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #e8eef3; }
blockquote { margin: 8px 0; padding: 6px 10px; background: #fff7e0; border-left: 4px solid #e0a800; }
a { color: #1f5f8b; text-decoration: none; }
code { font-family: Consolas, monospace; font-size: 9.5pt; }
hr { display: none; }
.salto { page-break-before: always; }
"""


def buscar_navegador() -> str:
    """Devuelve la ruta de Chrome o Edge para imprimir a PDF."""
    candidatos = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chrome") or "",
        shutil.which("msedge") or "",
    ]
    for ruta in candidatos:
        if ruta and Path(ruta).exists():
            return ruta
    sys.exit("No se encontró Chrome ni Edge. Defina la variable CHROME_PATH con la ruta del navegador.")


def enlaces_absolutos(md: str) -> str:
    """Convierte enlaces a páginas de la wiki, como (0.-Plan-del-Challenge-3), en URL completas."""
    return re.sub(r"\]\((?!https?://|#)([^)#\s]+)(#[^)]*)?\)",
                  lambda m: f"]({WIKI_URL}{m.group(1)}{m.group(2) or ''})", md)


def a_html(md: str, titulo: str) -> str:
    cuerpo = markdown.markdown(enlaces_absolutos(md), extensions=["tables", "sane_lists"])
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{titulo}</title>"
            f"<style>{CSS}</style></head><body><div class='encabezado'>{ENCABEZADO}</div>"
            f"{cuerpo}</body></html>")


def imprimir_pdf(navegador: str, html: str, salida: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        archivo = Path(tmp) / "acta.html"
        archivo.write_text(html, encoding="utf-8")
        subprocess.run(
            [navegador, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={Path(tmp) / 'perfil'}",
             f"--print-to-pdf={salida}", archivo.as_uri()],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        )
    if not salida.exists() or salida.stat().st_size == 0:
        sys.exit(f"No se pudo generar {salida}")


def main() -> None:
    if not ORIGEN.exists():
        sys.exit(f"No existe {ORIGEN}")
    texto = ORIGEN.read_text(encoding="utf-8")
    navegador = buscar_navegador()
    DESTINO.mkdir(parents=True, exist_ok=True)

    # Separar la introducción y cada acta (secciones "## Acta #N")
    partes = re.split(r"(?m)^(?=## Acta #\d+)", texto)
    intro, actas = partes[0], partes[1:]

    # Documento completo: introducción + cada acta en página nueva
    completo = intro + "".join(f"\n<div class='salto'></div>\n\n{a}" for a in actas)
    salida = DESTINO / "Actas_Challenge3_WaterGuard.pdf"
    imprimir_pdf(navegador, a_html(completo, "Actas Challenge #3"), salida)
    print(f"OK  {salida.relative_to(RAIZ)}")

    # Un PDF por acta
    for acta in actas:
        numero = re.match(r"## Acta #(\d+)", acta).group(1)
        salida = DESTINO / f"Acta_{numero}.pdf"
        imprimir_pdf(navegador, a_html(acta, f"Acta #{numero}"), salida)
        print(f"OK  {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
