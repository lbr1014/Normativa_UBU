from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from markitdown import MarkItDown


def posprocesado_markdown(text: str) -> str:
    """
    Limpieza básica del Markdown generado a partir de PDF.

    Ajusta aquí cualquier regla específica que veas que
    mejora tus pliegos u otros PDFs.
    """
    if not text:
        return ""

    # Unir palabras cortadas por guión al final de línea
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Colapsar saltos de línea múltiples
    text = re.sub(r"\n{2,}", "\n", text)

    # Quitar espacios en blanco al final de línea
    text = re.sub(r"[ \t]+\n", "\n", text)

    return text


def convertir_pdf(
    md_converter: MarkItDown,
    input_file: Path,
    input_root: Path,
    output_root: Path,
) -> None:
    """
    Convierte un PDF a Markdown.

    - input_root: carpeta raíz de entrada
    - output_root: carpeta raíz de salida
    """
    try:
        result = md_converter.convert(input_file)
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Error convirtiendo {input_file}: {exc}", file=sys.stderr)
        return

    # MarkItDown recomienda usar .markdown; si es None, usamos str(result)
    markdown = getattr(result, "markdown", None) or str(result)

    markdown = posprocesado_markdown(markdown)

    # Ruta relativa para mantener estructura de carpetas
    rel_path = input_file.relative_to(input_root)
    out_path = output_root / rel_path

    # 'archivo.pdf' -> 'archivo.md'
    out_path = out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    print(f"✓ {input_file} → {out_path}")


def directorio_pdf(
    input_path: Path,
    output_dir: Path,
    extensions: tuple[str, ...] = (".pdf",),
) -> None:
    """
    Convierte un único fichero o todos los PDFs de un directorio.
    """
    md = MarkItDown() 

    extensions = tuple(ext.lower() for ext in extensions)

    if input_path.is_file():
        if input_path.suffix.lower() not in extensions:
            print(
                f"{input_path} no tiene pdfs {extensions}",
                file=sys.stderr,
            )
            return
        convertir_pdf(md, input_path, input_path.parent, output_dir)
        return

    if not input_path.is_dir():
        print(f" La ruta de entrada no existe: {input_path}", file=sys.stderr)
        return

    # Directorio: se recorre recursivamente
    for file_path in input_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            convertir_pdf(md, file_path, input_path, output_dir)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convierte PDFs a Markdown usando MarkItDown.\n"
            "Si la entrada es un directorio, se recorre recursivamente."
        )
    )
    parser.add_argument(
        "input",
        help="Ruta al PDF o al directorio que contiene los PDFs de entrada",
    )
    parser.add_argument(
        "output",
        help="Directorio donde se guardarán los .md generados",
    )
    parser.add_argument(
        "--ext",
        nargs="*",
        default=[".pdf"],
        help="Extensiones a convertir (por defecto: .pdf). Ejemplo: --ext .pdf .PDF",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    extensions = tuple(args.ext)
    directorio_pdf(input_path, output_dir, extensions=extensions)


if __name__ == "__main__":
    main()
