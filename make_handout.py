#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


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


def load_config(config_path: Path) -> dict:
    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {config_path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in config file {config_path}: {e}")

    required_top_level = [
        "output_pages",
        "output_page",
        "slide",
        "trim_pt",
        "offset_pt",
        "latex",
        "cleanup",
    ]
    for key in required_top_level:
        if key not in config:
            raise SystemExit(f"Missing config key: {key}")

    return config


def get_base_output_page_settings(config: dict) -> tuple[float, float, float, float, float, float]:
    page = config["output_page"]

    page_width_in = float(page["width_in"])
    page_height_in = float(page["height_in"])

    margins = page["margins_in"]
    margin_left_in = float(margins["left"])
    margin_bottom_in = float(margins["bottom"])
    margin_right_in = float(margins["right"])
    margin_top_in = float(margins["top"])

    return (
        page_width_in,
        page_height_in,
        margin_left_in,
        margin_bottom_in,
        margin_right_in,
        margin_top_in,
    )


def get_effective_page_dimensions(config: dict) -> tuple[float, float]:
    page = config["output_page"]
    latex = config["latex"]

    width_in = float(page["width_in"])
    height_in = float(page["height_in"])
    landscape = bool(latex["landscape"])

    if landscape:
        return max(width_in, height_in), min(width_in, height_in)
    return min(width_in, height_in), max(width_in, height_in)


def get_effective_output_page_settings(config: dict) -> tuple[float, float, float, float, float, float]:
    (
        _base_width_in,
        _base_height_in,
        margin_left_in,
        margin_bottom_in,
        margin_right_in,
        margin_top_in,
    ) = get_base_output_page_settings(config)

    page_width_in, page_height_in = get_effective_page_dimensions(config)

    return (
        page_width_in,
        page_height_in,
        margin_left_in,
        margin_bottom_in,
        margin_right_in,
        margin_top_in,
    )


def get_slide_settings(config: dict) -> tuple[float, float]:
    slide = config["slide"]
    return float(slide["width_units"]), float(slide["height_units"])


def get_trim_settings(config: dict) -> tuple[float, float, float, float]:
    trim = config["trim_pt"]
    return (
        float(trim["left"]),
        float(trim["bottom"]),
        float(trim["right"]),
        float(trim["top"]),
    )


def get_offset_settings(config: dict) -> tuple[float, float]:
    offset = config["offset_pt"]
    return float(offset["x"]), float(offset["y"])


def scale(
    rows: int,
    cols: int,
    page_width_in: float,
    page_height_in: float,
    margin_left_in: float,
    margin_bottom_in: float,
    margin_right_in: float,
    margin_top_in: float,
    slide_width_units: float,
    slide_height_units: float,
) -> float:
    usable_w = page_width_in - margin_left_in - margin_right_in
    usable_h = page_height_in - margin_top_in - margin_bottom_in

    if usable_w <= 0 or usable_h <= 0:
        return 0.0

    cell_w = usable_w / cols
    cell_h = usable_h / rows
    return min(cell_w / slide_width_units, cell_h / slide_height_units)


def choose_best_grid(
    n: int,
    page_width_in: float,
    page_height_in: float,
    margin_left_in: float,
    margin_bottom_in: float,
    margin_right_in: float,
    margin_top_in: float,
    slide_width_units: float,
    slide_height_units: float,
) -> tuple[int, int, float]:
    best = None
    for rows in range(1, n + 1):
        cols = math.ceil(n / rows)
        s = scale(
            rows,
            cols,
            page_width_in,
            page_height_in,
            margin_left_in,
            margin_bottom_in,
            margin_right_in,
            margin_top_in,
            slide_width_units,
            slide_height_units,
        )
        cand = (s, rows, cols)
        if best is None or cand > best:
            best = cand

    if best is None:
        raise RuntimeError("Could not choose grid.")
    s, rows, cols = best
    return rows, cols, s


def choose_layout(total_slides: int, output_pages: int, config: dict) -> list[dict]:
    (
        page_width_in,
        page_height_in,
        margin_left_in,
        margin_bottom_in,
        margin_right_in,
        margin_top_in,
    ) = get_effective_output_page_settings(config)
    slide_width_units, slide_height_units = get_slide_settings(config)

    base = total_slides // output_pages
    remainder = total_slides % output_pages

    counts = []
    for i in range(output_pages):
        count = base + (1 if i < remainder else 0)
        counts.append(count)

    layout = []
    for count in counts:
        rows, cols, s = choose_best_grid(
            count,
            page_width_in,
            page_height_in,
            margin_left_in,
            margin_bottom_in,
            margin_right_in,
            margin_top_in,
            slide_width_units,
            slide_height_units,
        )
        layout.append(
            {
                "count": count,
                "rows": rows,
                "cols": cols,
                "scale": s,
            }
        )

    return layout


def latex_escape_path(path_str: str) -> str:
    return path_str.replace("\\", "/")


def build_geometry_margin_string(config: dict) -> str:
    page = config["output_page"]
    margins = page["margins_in"]
    return (
        f"left={margins['left']}in,"
        f"bottom={margins['bottom']}in,"
        f"right={margins['right']}in,"
        f"top={margins['top']}in"
    )


def write_tex(tex_path: Path, combined_pdf_name: str, layout: list[dict], config: dict) -> None:
    trim_left, trim_bottom, trim_right, trim_top = get_trim_settings(config)
    offset_x, offset_y = get_offset_settings(config)

    latex = config["latex"]
    paper_size = latex["paper_size"]
    frame = "true" if latex["frame"] else "false"
    column = "true" if latex["column_major_order"] else "false"
    delta_x = float(latex["delta_pt"]["x"])
    delta_y = float(latex["delta_pt"]["y"])

    effective_width_in, effective_height_in = get_effective_page_dimensions(config)

    trim_str = f"{trim_left} {trim_bottom} {trim_right} {trim_top}"

    geometry_parts = []
    if paper_size == "custom":
        geometry_parts.append(f"paperwidth={effective_width_in}in")
        geometry_parts.append(f"paperheight={effective_height_in}in")
    else:
        geometry_parts.append(paper_size)
        if bool(latex["landscape"]):
            geometry_parts.append("landscape")

    geometry_parts.append(build_geometry_margin_string(config))
    geometry_options = ",".join(geometry_parts)

    blocks = []
    start = 1

    for page_layout in layout:
        count = page_layout["count"]
        rows = page_layout["rows"]
        cols = page_layout["cols"]
        end = start + count - 1

        block = rf"""\includepdf[
  pages={{{start}-{end}}},
  nup={cols}x{rows},
  delta={delta_x} {delta_y},
  offset={offset_x} {offset_y},
  frame={frame},
  column={column},
  trim={trim_str},
  clip=true
]{{{latex_escape_path(combined_pdf_name)}}}
"""
        blocks.append(block)
        start = end + 1

    tex = rf"""\documentclass{{article}}
\usepackage[{geometry_options}]{{geometry}}
\usepackage{{pdfpages}}
\pagestyle{{empty}}

\begin{{document}}

{''.join(blocks)}\end{{document}}
"""
    tex_path.write_text(tex, encoding="utf-8")


def main():
    if len(sys.argv) < 4:
        print(
            "Usage:\n"
            "  python3 make_handout.py CONFIG.json output.pdf lecture1.pdf lecture2.pdf [lecture3.pdf ...]"
        )
        sys.exit(1)

    config_path = Path(sys.argv[1]).resolve()
    output_pdf = Path(sys.argv[2]).resolve()
    input_pdfs = [Path(p).resolve() for p in sys.argv[3:]]
    workdir = output_pdf.parent

    config = load_config(config_path)

    output_pages = int(config["output_pages"])
    if output_pages < 1:
        raise SystemExit("config.output_pages must be at least 1")

    require_command("pdfinfo")
    require_command("pdfunite")
    require_command("pdflatex")

    for pdf in input_pdfs:
        if not pdf.exists():
            raise SystemExit(f"Missing file: {pdf}")

    counts = [pdf_page_count(pdf) for pdf in input_pdfs]
    total_slides = sum(counts)

    if total_slides < output_pages:
        raise SystemExit(f"Need at least {output_pages} total slides.")

    print("Using config:", config_path.name)
    print("\nInput files and slide counts:")
    for pdf, count in zip(input_pdfs, counts):
        print(f"  {pdf.name}: {count}")
    print(f"Total slides: {total_slides}")

    effective_width_in, effective_height_in = get_effective_page_dimensions(config)
    print(f"\nEffective output page size: {effective_width_in}in x {effective_height_in}in")

    layout = choose_layout(total_slides, output_pages, config)

    print("\nChosen layout:")
    running_total = 0
    for i, page_layout in enumerate(layout, start=1):
        count = page_layout["count"]
        rows = page_layout["rows"]
        cols = page_layout["cols"]
        start = running_total + 1
        end = running_total + count
        print(f"  Page {i}: slides {start}-{end} in {rows} rows x {cols} cols")
        running_total = end

    trim_left, trim_bottom, trim_right, trim_top = get_trim_settings(config)
    print("\nTrim applied to every slide:")
    print(
        f"  left={trim_left} pt, bottom={trim_bottom} pt, "
        f"right={trim_right} pt, top={trim_top} pt"
    )

    offset_x, offset_y = get_offset_settings(config)
    print(f"Offset: x={offset_x} pt, y={offset_y} pt")

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
    write_tex(tex_file, combined_pdf.name, layout, config)

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

    cleanup = bool(config["cleanup"])
    if cleanup:
        for extra in [aux_file, log_file, tex_file]:
            if extra.exists():
                extra.unlink()


if __name__ == "__main__":
    main()