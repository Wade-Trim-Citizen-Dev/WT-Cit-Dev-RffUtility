# RFF Utilities

A Windows desktop toolkit (with CLIs) for **SWMM5-RAIN `.rff` binary rainfall
files** — read, visualize, export, and merge. Formerly *RFF Merger*.

- **Read** — parse the binary format and list each gauge's interval and
  record count.
- **Visualize** — per-gauge statistics and interactive rainfall plots,
  including a cumulative view.
- **Export** — convert gauge data to CSV, SWMM rain data (`.dat`), or JSON.
- **Merge** — combine multiple `.rff` files into one. When two files contain
  data for the same gauge at the same timestamp, the file **later in the merge
  order wins** — so you can layer corrected/newer data on top of older data.

## Features

- Drag-and-drop GUI to add and reorder `.rff` files (PyQt5).
- Per-gauge statistics and an interactive rainfall plot (pyqtgraph), with a
  per-file gauge browser, a cumulative-rainfall view, a value table beside the
  plot (date/time, rainfall, cumulative — Ctrl+C copies selected rows), and a
  progress bar while files are analyzed (numpy-backed reads — a 40 MB file
  takes well under a second locally).
- Export any `.rff` file to CSV (long, wide, or one file per gauge), SWMM
  user-prepared rain data (`.dat`), or JSON — all gauges or a checked subset.
- Background merge with a progress bar.
- Standalone CLIs for batch/scripted merging (`merge_rff.py`) and exporting
  (`export_rff.py`).
- Filename-aware ordering: files with `YYYY` and `Q1`–`Q4` in their names sort
  chronologically by default in the CLI.

## Installation (run from source)

Requires Python 3.8+.

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### GUI

```bat
python main.py
```

1. Drag `.rff` files into the list (or use **Add Files**). Every tool works on
   the files in this list.
2. **Visualize / Statistics** — per-gauge stats across all listed files; pick a
   file and gauge to plot, toggle **Cumulative** for a running total. A table
   beside the plot lists every record (date/time, rainfall, cumulative);
   select rows and press Ctrl+C to copy them.
3. **Export…** — convert a file to CSV/`.dat`/JSON, all gauges or a checked
   subset.
4. **Merge** — choose an output path in the Merge box and click **Merge
   Files**. Reorder inputs by dragging — files lower in the list overwrite
   higher ones on overlapping timestamps.

### CLI — merging

Merge every `.rff` in a folder into one file:

```bat
python merge_rff.py --folder "C:\path\to\rff_files" -o "C:\path\to\merged.rff"
```

| Option | Description |
| --- | --- |
| `--folder` | Folder containing the `.rff` files to merge (required). |
| `-o`, `--output` | Output `.rff` path (required). |
| `--recursive` | Search subfolders for `.rff` files. |
| `--progress-every N` | Print progress every N gauges (default: 25). |

In the CLI, inputs are sorted by `(year, quarter, filename)` parsed from the
file names, so `2018_Q2`, `2018_Q3`, `2018_Q4` merge in calendar order.

### CLI — exporting

```bat
python export_rff.py input.rff --list
python export_rff.py input.rff -o rainfall.csv
python export_rff.py input.rff -o rainfall.dat --gauges GAGEA01C1,GAGEA02C1
python export_rff.py input.rff -o rainfall.csv -f csv-wide
python export_rff.py input.rff -o rainfall.csv -f csv-split
```

| Option | Description |
| --- | --- |
| `-o`, `--output` | Output file path (for `csv-split`, the base name for the per-gauge files). |
| `-f`, `--format` | `csv`, `csv-wide`, `csv-split`, `dat`, or `json` (default: inferred from the output extension, else `csv`). |
| `--gauges` | Comma-separated gauge IDs to export (default: all). |
| `--list` | List the file's gauges (ID, interval, record count) and exit. |

Formats:

- **`csv`** — one row per reading: `gauge_id, datetime, value`.
- **`csv-wide`** — one row per timestamp, one column per gauge (blank where a
  gauge has no reading).
- **`csv-split`** — one file per gauge with `datetime, value` rows, written
  next to the output path as `<name>_<gauge>.csv` (gauges with no data get a
  header-only file; characters not allowed in filenames become `_`).
- **`dat`** — SWMM5 user-prepared rain data, directly usable as a rain gage
  data file: `station year month day hour minute value`.
- **`json`** — one object per gauge with `id`, `interval_seconds`,
  `record_count`, and `[datetime, value]` records.

Timestamps are written as `YYYY-MM-DD HH:MM:SS`, rounded to the nearest second
to remove floating-point jitter from the Excel day serials stored in the file.

## The `.rff` file format

This format was reverse-engineered; the tools assume the following layout
(little-endian):

| Section | Bytes | Contents |
| --- | --- | --- |
| Magic | 10 | ASCII `SWMM5-RAIN` |
| Gauge count | 4 | `uint32` number of gauges |
| Gauge directory | `gauge_count × 1037` | one block per gauge |
| Gauge data | remainder | record streams referenced by the directory |

Each **1037-byte directory block**:

- bytes `0..16` — gauge ID (null-padded ASCII)
- last 16 bytes — four `uint32`s: `unk0`, `interval_seconds`,
  `start_offset`, `end_offset` (byte offsets of this gauge's data)

Each **12-byte data record**: a `float64` time (Excel day serial, origin
1899-12-30) followed by a `float32` rainfall value.

Inputs must be compatible to merge: same gauge count, same gauge IDs in the same
order, and matching reporting intervals.

## Building the executable

```bat
build_exe.bat
```

This installs PyInstaller into `venv` and produces `dist\RFF_Utilities.exe`
(single-file, windowed). A previous build, if present, is archived with a
timestamp.

## Tests

```bat
python -m unittest discover -p "test_*.py"
```

`smoke_gui.py` is an offscreen GUI smoke test (instantiates the real dialogs
against the `examples/` files); run it with the project venv after UI changes.

The `examples/` folder contains sample quarterly 2018 rainfall files you can use
to try the merge and visualization workflows.

## Credits

Ross Volkwein — Wade Trim.
