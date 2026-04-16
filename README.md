# slides-to-cheat-sheet
# Cheat Sheet / Handout Generator

This script combines multiple lecture slide PDFs into one output PDF handout.

## What to put in the folder

Put these files in the same folder:

- `make_handout.py`
- `handout_config.json`
- your lecture slide PDFs, for example:
  - `lecture1.pdf`
  - `lecture2.pdf`
  - `lecture3.pdf`

## What to edit

Open `handout_config.json` and set the values you want.

### What each setting means

- `output_pages`  
  How many pages the final handout PDF should have.

- `output_page.width_in`, `output_page.height_in`  
  The size of each output page, in inches.  
  Example: `11.0` by `8.5` for landscape letter.

- `output_page.margins_in.left`, `bottom`, `right`, `top`  
  The outer margins on the final handout pages, in inches.

- `slide.width_units`, `slide.height_units`  
  The slide aspect ratio.  
  Use:
  - `16` and `9` for most modern slides
  - `4` and `3` for older slides

- `trim_pt.left`, `bottom`, `right`, `top`  
  How much to crop off each slide **before** placing it in the handout.  
  Units are **points**.  
  `72 points = 1 inch`.  
  Use `0` if you do not want any cropping.

- `offset_pt.x`, `offset_pt.y`  
  Shifts the whole slide grid on the output page.  
  Usually leave these at `0` unless you need to nudge the layout.

- `latex.paper_size`  
  Usually leave as `"custom"`.

- `latex.landscape`  
  `true` for landscape pages, `false` for portrait.

- `latex.frame`  
  `true` draws borders around slides.  
  Usually leave as `false`.

- `latex.column_major_order`  
  If `true`, slides are placed **top to bottom, then left to right**.  
  Usually leave this as `true`.

- `latex.delta_pt.x`, `latex.delta_pt.y`  
  Space between slides, in points.  
  Use `0` and `0` for no extra gap.

- `cleanup`  
  If `true`, temporary files like `.log` and generated `.tex` are deleted after the script runs.

## How to run it

Open Terminal, go into the folder, and run (for as many slideshow files as you want):

```bash
python3 make_handout.py handout_config.json <desired output filename> <slideshow 1 file name> <slideshow 2 file name> <slideshow ... file name> ...
```

Example:
```bash
python3 make_handout.py handout_config.json cs_101_cheat_sheet.pdf lecture1.pdf lecture2.pdf lecture3.pdf
```