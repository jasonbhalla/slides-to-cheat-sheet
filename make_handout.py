#!/usr/bin/env python3
from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path


# ---------- USER SETTINGS ----------

# Number of output pages in the final handout PDF
OUTPUT_PAGES = 4

# Output page size: US Letter landscape
PAGE_W_IN = 11.0
PAGE_H_IN = 8.5

# Outer page margins on the handout pages
MARGIN_IN = 0.25

# Assumed slide aspect ratio
# Use 16/9 for most modern slides, 4/3 for older slides
SLIDE_W = 16
SLIDE_H = 9

# Trim values applied to EVERY slide before placement, in PDF points:
# trim = left bottom right top
# For NO cutoff, set all to 0
TRIM_LEFT = 0
TRIM_BOTTOM = 0
TRIM_RIGHT = 0
TRIM_TOP = 0

# Optional horizontal/vertical offset of the whole n-up block, in points
# Leave at 0 unless you specifically need to push the block inward.
OFFSET_X = 0
OFFSET_Y = 0

# ----------------------------------


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required command not found: {name}")


def pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        text=True,
        capture_output=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"Could not determine page count for {pdf_path}")


def scale(rows: int, cols: int) -> float:
    usable_w = PAGE_W_IN - 2 * MARGIN_IN
    usable_h = PAGE_H_IN - 2 * MARGIN_IN
    cell_w = usable_w / cols
    cell_h = usable_h / rows
    return min(cell_w / SLIDE_W, cell_h / SLIDE_H)


def choose_best_grid(n: int) -> tuple[int, int, float]:
    """
    For a page containing n slides, choose rows/cols that maximize slide scale.
    Returns (rows, cols, scale).
    """
    best = None
    for rows in range(1, n + 1):
        cols = math.ceil(n / rows)
        s = scale(rows, cols)
        cand = (s, rows, cols)
        if best is None or cand > best:
            best = cand

    if best is None:
        raise RuntimeError("Could not choose grid.")
    s, rows, cols = best
    return rows, cols, s


def choose_layout(total_slides: int, output_pages: int):
    """
    Split total slides across output_pages as evenly as possible,
    then choose the best grid for each page independently.

    Returns a list of dicts:
      [
        {"count": ..., "rows": ..., "cols": ...},
        ...
      ]
    """
    base = total_slides // output_pages
    remainder = total_slides % output_pages

    counts = []
    for i in range(output_pages):
        count = base + (1 if i < remainder else 0)
        counts.append(count)

    layout = []
    for count in counts:
        rows, cols, s = choose_best_grid(count)
        layout.append(
            {
                "count": count,
                "rows": rows,
                "cols": cols,
                "scale": s,
            }
        )

    return layout


def write_tex(
    tex_path: Path,
    combined_pdf_name: str,
    layout: list[dict],
) -> None:
    trim_str = f"{TRIM_LEFT} {TRIM_BOTTOM} {TRIM_RIGHT} {TRIM_TOP}"

    blocks = []
    start = 1

    for page in layout:
        count = page["count"]
        rows = page["rows"]
        cols = page["cols"]
        end = start + count - 1

        block = rf"""\includepdf[
  pages={{{start}-{end}}},
  nup={cols}x{rows},
  delta=0 0,
  offset={OFFSET_X} {OFFSET_Y},
  frame=false,
  column=true,
  trim={trim_str},
  clip=true
]{{{combined_pdf_name}}}
"""
        blocks.append(block)
        start = end + 1

    tex = rf"""\documentclass{{article}}
\usepackage[letterpaper,landscape,margin=0.25in]{{geometry}}
\usepackage{{pdfpages}}
\pagestyle{{empty}}

\begin{{document}}

{''.join(blocks)}
\end{{document}}
"""
    tex_path.write_text(tex, encoding="utf-8")


def main():
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "  python3 make_handout.py output.pdf lecture1.pdf lecture2.pdf [lecture3.pdf ...]"
        )
        sys.exit(1)

    output_pdf = Path(sys.argv[1]).resolve()
    input_pdfs = [Path(p).resolve() for p in sys.argv[2:]]
    workdir = output_pdf.parent

    require_command("pdfinfo")
    require_command("pdfunite")
    require_command("pdflatex")

    for pdf in input_pdfs:
        if not pdf.exists():
            raise SystemExit(f"Missing file: {pdf}")

    counts = [pdf_page_count(pdf) for pdf in input_pdfs]
    total_slides = sum(counts)

    if total_slides < OUTPUT_PAGES:
        raise SystemExit(f"Need at least {OUTPUT_PAGES} total slides.")

    print("Input files and slide counts:")
    for pdf, count in zip(input_pdfs, counts):
        print(f"  {pdf.name}: {count}")
    print(f"Total slides: {total_slides}")

    layout = choose_layout(total_slides, OUTPUT_PAGES)

    print("\nChosen layout:")
    running_total = 0
    for i, page in enumerate(layout, start=1):
        count = page["count"]
        rows = page["rows"]
        cols = page["cols"]
        start = running_total + 1
        end = running_total + count
        print(
            f"  Page {i}: slides {start}-{end} "
            f"in {rows} rows x {cols} cols"
        )
        running_total = end

    print("\nTrim applied to every slide:")
    print(
        f"  left={TRIM_LEFT} pt, bottom={TRIM_BOTTOM} pt, "
        f"right={TRIM_RIGHT} pt, top={TRIM_TOP} pt"
    )

    combined_pdf = workdir / "combined.pdf"
    tex_file = workdir / "handout.tex"
    aux_file = workdir / "handout.aux"
    log_file = workdir / "handout.log"
    produced_pdf = workdir / "handout.pdf"

    print("\nCombining PDFs...")
    subprocess.run(
        ["pdfunite", *[str(p) for p in input_pdfs], str(combined_pdf)],
        check=True,
        text=True,
        cwd=workdir,
    )

    print("Writing LaTeX file...")
    write_tex(tex_file, combined_pdf.name, layout)

    print("Running pdflatex...")
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", tex_file.name],
        check=True,
        text=True,
        cwd=workdir,
    )

    if not produced_pdf.exists():
        raise SystemExit("pdflatex finished, but handout.pdf was not created.")

    if output_pdf.exists():
        output_pdf.unlink()
    produced_pdf.replace(output_pdf)

    print(f"\nDone.")
    print(f"Created: {output_pdf}")

    for extra in [aux_file, log_file, tex_file]:
        if extra.exists():
            extra.unlink()


if __name__ == "__main__":
    main()