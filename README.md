# RFF Merger

A Windows desktop utility (with a CLI) for working with **SWMM5-RAIN `.rff`
binary rainfall files**. It merges multiple `.rff` files into a single file and
lets you preview rainfall statistics and per-gauge time series before merging.

When two files contain data for the same gauge at the same timestamp, the file
**later in the merge order wins** — so you can layer corrected/newer data on top
of older data.

## Features

- Drag-and-drop GUI to add and reorder `.rff` files (PyQt5).
- Per-gauge statistics and an interactive rainfall plot (pyqtgraph).
- Background merge with a progress bar.
- Standalone CLI for batch/scripted merging of a whole folder.
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

1. Drag `.rff` files into the list (or use **Add Files**). Reorder by dragging —
   files higher in the list are processed first; lower files overwrite higher
   ones on overlapping timestamps.
2. Choose an output file.
3. Click **Visualize / Statistics** to preview, or **Merge Files** to write the
   merged output.

### CLI

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

## The `.rff` file format

This format was reverse-engineered; the merger assumes the following layout
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

This installs PyInstaller into `venv` and produces `dist\RFF_Merger.exe`
(single-file, windowed). A previous build, if present, is archived with a
timestamp.

## Tests

```bat
python -m unittest test_merge.py
```

The `examples/` folder contains sample quarterly 2018 rainfall files you can use
to try the merge and visualization workflows.

## Credits

Ross Volkwein — Wade Trim.
