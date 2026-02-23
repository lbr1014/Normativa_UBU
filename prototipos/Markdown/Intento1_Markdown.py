from __future__ import annotations

import re
import sys
from pathlib import Path

from markitdown import MarkItDown

# Títulos (líneas en mayusculas)
TITULOS = re.compile(
    r"^[A-ZÁÉÍÓÚÜÑ0-9 .,:;/()\-]{8,}$"
)

# Secciones con números romanos (I., II., III., ...)
SECCIONES = re.compile(
    r"^(?P<num>[IVXLCDM]+)\.\s*$"
)

# Secciones tipo G.2.2. (letra + numéricos)
SECCIONES_ALFANUM = re.compile(
    r"^(?P<code>[A-Z](?:\.\d+)+\.)\s*$"
)

# Sección numérica con solo un número: "1."
SECCION_NUM_SIMPLE = re.compile(
    r"^(?P<num>\d+)\.\s*$"
)

# Sección numérica compuesta: "1.1", "1.1.", "1.2.3", ...
SECCION_NUM_COMPUESTA = re.compile(
    r"^(?P<num>\d+(?:\.\d+)+)\.?\s*$"
)

# Subtítulos tipo "1. Introducción" o "1.2.3 Algo"
SUBTITULOS = re.compile(
    r"^(?P<num>\d+(?:\.\d+)*)\.\s+(?P<title>.+)$"
)

# Detecta líneas del índice
INDICE = re.compile(
    r"^(?P<title>.+?)\s?\.{5,}\s?(?P<page>\d+)$"
)


def posprocesado_markdown(text: str) -> str:
    """
    Limpieza básica del Markdown generado a partir de PDF.
    """
    if not text:
        return ""

    # Eliminar viñetas
    BULLET_CHARS = "•◦·▪▫●"
    for ch in BULLET_CHARS:
        text = text.replace(ch, "")

    # Unir palabras cortadas
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Sustituir saltos de linea simples por espacios
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Colapsar saltos de línea múltiples
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Quitar espacios finales
    text = re.sub(r"[ \t]+\n", "\n", text)

    # Dividir líneas para procesar índice
    lines = text.splitlines()
    lines = procesar_indice(lines)

    # Volver a unir para procesar títulos
    text = "\n".join(lines)

    # Detectar títulos y secciones y marcarlos como headings
    text = titulos_markdown(text)

    return text


# ===================== TÍTULOS ===========================
def titulos_markdown(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    main_title_done = False

    i = 0
    while i < len(lines):
        line = lines[i]
        raw = line.rstrip("\n")
        stripped = raw.strip()

        # Las línea vacías las dejamos tal cual
        if not stripped:
            out.append(line)
            i += 1
            continue

        # Si ya es un heading markdown (cualquier nivel)
        if stripped.startswith("#"):
            out.append(line)
            i += 1
            continue

        # Secciones con números romanos (I. II. ...)
        m_rom = SECCIONES.match(stripped)
        if m_rom and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.strip()

            if TITULOS.match(next_stripped):
                # Sección de nivel 2
                sec_num = m_rom.group("num")
                out.append(f"\n## {sec_num}. {next_stripped}\n")
                # Saltamos la línea siguiente
                i += 2
                continue

        # Secciones tipo G.2.2. seguidas de un título en mayúsculas
        m_alpha = SECCIONES_ALFANUM.match(stripped)
        if m_alpha and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.strip()

            if TITULOS.match(next_stripped):
                code = m_alpha.group("code")
                # También las marcamos como H2
                out.append(f"\n## {code} {next_stripped}\n")
                i += 2
                continue

        # Secciones numéricas en línea independiente

        # Título si la siguiente línea está en mayúsculas
        m_simple = SECCION_NUM_SIMPLE.match(stripped)
        if m_simple and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.strip()

            if TITULOS.match(next_stripped):
                num = m_simple.group("num")
                out.append(f"\n## {num}. {next_stripped}\n")
                i += 2
                continue
            # Si la siguiente línea no es mayúscula, no lo tratamos como título

        # Caso 2: "1.1", "1.1.", "1.2.3", siempre es título sin mirar mayúsculas
        m_compuesta = SECCION_NUM_COMPUESTA.match(stripped)
        if m_compuesta and i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.strip()

            num = m_compuesta.group("num")
            out.append(f"\n## {num}. {next_stripped}\n")
            i += 2
            continue

        # Subtítulos (1. 1.1, con texto en la misma línea)
        m_num = SUBTITULOS.match(stripped)
        if m_num:
            out.append(f"### {stripped}")
            i += 1
            continue

        # Líneas en mayúsculas
        if TITULOS.match(stripped):
            # Primer título lo tomamos como H1
            if not main_title_done and i < 15:
                level = 1
                main_title_done = True
            else:
                # El resto H2
                level = 2

            out.append(f"\n{'#' * level} {stripped}\n")
            i += 1
            continue

        # En cualquier otro caso, lo dejamos tal cual
        out.append(line)
        i += 1

    return "\n".join(out)


# ============================= ÍNDICE =============================
def slugify(title: str) -> str:
    """Convierte un título en un ancla markdown."""
    title = title.lower()
    title = re.sub(r"[^a-z0-9áéíóúñü ]+", "", title)
    title = title.strip().replace(" ", "-")
    return title


def procesar_indice(lines: list[str]) -> list[str]:
    """
    Procesa el índice del PDF convirtiendo cada entrada en:
    - [TÍTULO](#ancla)
    """
    out = []
    for line in lines:
        m = INDICE.match(line.strip())
        if m:
            titulo = m.group("title")
            ancla = slugify(titulo)
            out.append(f"- [{titulo}](#{ancla})")
        else:
            out.append(line)
    return out


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
    except Exception as exc:  
        print(f"✗ Error convirtiendo {input_file}: {exc}", file=sys.stderr)
        return

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
    Convierte todos los PDFs de un directorio (recursivo).
    """
    md = MarkItDown()

    extensions = tuple(ext.lower() for ext in extensions)

    if not input_path.is_dir():
        print(
            f"La ruta de entrada no existe o no es un directorio: {input_path}",
            file=sys.stderr,
        )
        return

    # Directorio: se recorre recursivamente
    for file_path in input_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            convertir_pdf(md, file_path, input_path, output_dir)


def main() -> None:
    # Carpeta de entrada (relativa al directorio desde el que se ejecuta el script)
    input_path = Path("pdfs").resolve()
    # Carpeta de salida
    output_dir = Path("markdown_intento1").resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    extensions = (".pdf",)
    directorio_pdf(input_path, output_dir, extensions=extensions)


if __name__ == "__main__":
    main()
