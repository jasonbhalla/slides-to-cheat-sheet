#!/usr/bin/env python3
from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path


# ---------- USER SETTINGS ----------

# Output page size: US Letter landscape
PAGE_W_IN = 11.0
PAGE_H_IN = 8.5

# Outer page margins on the handout pages
MARGIN_IN = 0

# Assumed slide aspect ratio
# Use 16/9 for most modern slides, 4/3 for older slides
SLIDE_W = 16
SLIDE_H = 9

# Trim values applied to EVERY slide before placement, in PDF points:
# trim = left bottom right top
#
# 72 pt = 1 inch
# 18 pt = 0.25 inch
# 24 pt = 0.333 inch
# 36 pt = 0.5 inch
#
# Adjust these as needed.
# Note to SELF: I opened the PDF in affinity publisher, measured the margins of the slides, and the pt for those was what I put for the trim.
TRIM_LEFT = 73.2
TRIM_BOTTOM = 40.7
TRIM_RIGHT = 73.2
TRIM_TOP = 63.4

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


def choose_layout(total_slides: int):
    best = None

    for k in range(1, total_slides):
        n1 = k
        n2 = total_slides - k

        for r1 in range(1, n1 + 1):
            c1 = math.ceil(n1 / r1)
            s1 = scale(r1, c1)

            for r2 in range(1, n2 + 1):
                c2 = math.ceil(n2 / r2)
                s2 = scale(r2, c2)

                score = (min(s1, s2), s1 + s2)
                candidate = (score, n1, r1, c1, n2, r2, c2)

                if best is None or candidate > best:
                    best = candidate

    if best is None:
        raise RuntimeError("Could not choose a layout.")

    _, n1, r1, c1, n2, r2, c2 = best
    return n1, r1, c1, n2, r2, c2


def write_tex(
    tex_path: Path,
    combined_pdf_name: str,
    n1: int,
    r1: int,
    c1: int,
    n2: int,
    r2: int,
    c2: int,
) -> None:
    start2 = n1 + 1
    end2 = n1 + n2

    trim_str = f"{TRIM_LEFT} {TRIM_BOTTOM} {TRIM_RIGHT} {TRIM_TOP}"

    tex = rf"""\documentclass{{article}}
\usepackage[letterpaper,landscape,margin=0.25in]{{geometry}}
\usepackage{{pdfpages}}
\pagestyle{{empty}}

\begin{{document}}

\includepdf[
  pages={{1-{n1}}},
  nup={c1}x{r1},
  delta=0 0,
  frame=false,
  column=true,
  trim={trim_str},
  clip=true
]{{{combined_pdf_name}}}

\includepdf[
  pages={{{start2}-{end2}}},
  nup={c2}x{r2},
  delta=0 0,
  frame=false,
  column=true,
  trim={trim_str},
  clip=true
]{{{combined_pdf_name}}}

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

    if total_slides < 2:
        raise SystemExit("Need at least 2 total slides.")

    print("Input files and slide counts:")
    for pdf, count in zip(input_pdfs, counts):
        print(f"  {pdf.name}: {count}")
    print(f"Total slides: {total_slides}")

    n1, r1, c1, n2, r2, c2 = choose_layout(total_slides)

    print("\nChosen layout:")
    print(f"  Page 1: first {n1} slides in {r1} rows x {c1} cols")
    print(f"  Page 2: next  {n2} slides in {r2} rows x {c2} cols")

    print("\nTrim applied to every slide:")
    print(f"  left={TRIM_LEFT} pt, bottom={TRIM_BOTTOM} pt, right={TRIM_RIGHT} pt, top={TRIM_TOP} pt")

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
    write_tex(tex_file, combined_pdf.name, n1, r1, c1, n2, r2, c2)

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

    # Cleanup temporary files
    for extra in [aux_file, log_file, tex_file]:
        if extra.exists():
            extra.unlink()


if __name__ == "__main__":
    main()