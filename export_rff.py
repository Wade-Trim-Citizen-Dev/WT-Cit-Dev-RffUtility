#!/usr/bin/env python3
"""
export_rff.py

Export gauge data from a SWMM5-RAIN .rff binary rainfall file to text formats.

Supported formats:
- csv       One row per reading: gauge_id, datetime, value
- csv-wide  One row per timestamp, one column per gauge (blank = no reading)
- dat       SWMM5 user-prepared rain data: station year month day hour minute value
- json      {"source": ..., "gauges": [{"id", "interval_seconds", "records"}, ...]}

Uses only the standard library so the PyInstaller build stays small.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from merge_rff import (EXCEL_EPOCH, GaugeDirEntry, RECORD_SIZE,
                       read_gauge_records, read_rff_header_and_directory)

ProgressCallback = Optional[Callable[[int, int, str], None]]

FORMATS = ("csv", "csv-wide", "dat", "json")

# Map output-file extensions to a default format for CLI/GUI convenience.
EXTENSION_FORMATS = {
    ".csv": "csv",
    ".dat": "dat",
    ".txt": "dat",
    ".json": "json",
}


def excel_to_rounded_datetime(excel_date: float) -> datetime.datetime:
    """Excel serial -> datetime, rounded to the nearest second.

    Day serials are float64, so interval boundaries can land at e.g.
    11:59:59.999999; rounding keeps exported timestamps clean.
    """
    return EXCEL_EPOCH + datetime.timedelta(seconds=round(excel_date * 86400.0))


def format_value(value: float) -> str:
    # float32 carries ~7 significant digits; %.6g drops the float64 noise.
    return f"{value:.6g}"


def select_gauges(directory: List[GaugeDirEntry],
                  gauges: Optional[List[str]]) -> List[GaugeDirEntry]:
    """Filter a directory to the requested gauge IDs, preserving file order."""
    if gauges is None:
        return list(directory)
    wanted = set(gauges)
    known = {e.gauge_id for e in directory}
    unknown = sorted(wanted - known)
    if unknown:
        raise ValueError(f"Unknown gauge IDs: {', '.join(unknown)}")
    return [e for e in directory if e.gauge_id in wanted]


def _iter_selected(input_path: str, gauges: Optional[List[str]],
                   progress_callback: ProgressCallback):
    rff = read_rff_header_and_directory(input_path)
    entries = select_gauges(rff.directory, gauges)
    with open(input_path, "rb") as fh:
        for i, entry in enumerate(entries):
            if progress_callback:
                progress_callback(i + 1, len(entries), entry.gauge_id)
            yield entry, read_gauge_records(input_path, entry, fh=fh)


def export_csv(input_path: str, output_path: str,
               gauges: Optional[List[str]] = None,
               progress_callback: ProgressCallback = None) -> None:
    """Long CSV: gauge_id, datetime, value — one row per reading."""
    with open(output_path, "w", encoding="utf-8", newline="") as out:
        out.write("gauge_id,datetime,value\n")
        for entry, recs in _iter_selected(input_path, gauges, progress_callback):
            gid = _csv_field(entry.gauge_id)
            for t, v in recs:
                out.write(f"{gid},{excel_to_rounded_datetime(t):%Y-%m-%d %H:%M:%S},{format_value(v)}\n")


def export_csv_wide(input_path: str, output_path: str,
                    gauges: Optional[List[str]] = None,
                    progress_callback: ProgressCallback = None) -> None:
    """Wide CSV: one row per timestamp, one column per gauge."""
    columns: List[str] = []
    by_time: Dict[float, Dict[str, float]] = {}
    for entry, recs in _iter_selected(input_path, gauges, progress_callback):
        columns.append(entry.gauge_id)
        for t, v in recs:
            by_time.setdefault(t, {})[entry.gauge_id] = v

    with open(output_path, "w", encoding="utf-8", newline="") as out:
        out.write("datetime," + ",".join(_csv_field(c) for c in columns) + "\n")
        for t in sorted(by_time):
            row = by_time[t]
            cells = (format_value(row[c]) if c in row else "" for c in columns)
            out.write(f"{excel_to_rounded_datetime(t):%Y-%m-%d %H:%M:%S}," + ",".join(cells) + "\n")


def export_dat(input_path: str, output_path: str,
               gauges: Optional[List[str]] = None,
               progress_callback: ProgressCallback = None) -> None:
    """SWMM5 user-prepared rain data: station year month day hour minute value."""
    with open(output_path, "w", encoding="utf-8", newline="") as out:
        for entry, recs in _iter_selected(input_path, gauges, progress_callback):
            for t, v in recs:
                dt = excel_to_rounded_datetime(t)
                out.write(f"{entry.gauge_id} {dt.year} {dt.month:02d} {dt.day:02d} "
                          f"{dt.hour:02d} {dt.minute:02d} {format_value(v)}\n")


def export_json(input_path: str, output_path: str,
                gauges: Optional[List[str]] = None,
                progress_callback: ProgressCallback = None) -> None:
    """JSON with one object per gauge; records are [datetime, value] pairs.

    Written gauge-by-gauge so memory stays bounded by the largest gauge.
    """
    with open(output_path, "w", encoding="utf-8") as out:
        out.write('{"source": %s, "gauges": [' % json.dumps(Path(input_path).name))
        first = True
        for entry, recs in _iter_selected(input_path, gauges, progress_callback):
            gauge_obj = {
                "id": entry.gauge_id,
                "interval_seconds": entry.interval_seconds,
                "record_count": len(recs),
                "records": [
                    [f"{excel_to_rounded_datetime(t):%Y-%m-%d %H:%M:%S}", float(format_value(v))]
                    for t, v in recs
                ],
            }
            out.write(("" if first else ",\n") + json.dumps(gauge_obj))
            first = False
        out.write("]}\n")


def _csv_field(text: str) -> str:
    if any(ch in text for ch in ',"\n\r'):
        return '"' + text.replace('"', '""') + '"'
    return text


_EXPORTERS = {
    "csv": export_csv,
    "csv-wide": export_csv_wide,
    "dat": export_dat,
    "json": export_json,
}


def export_rff_file(input_path: str, output_path: str, fmt: str,
                    gauges: Optional[List[str]] = None,
                    progress_callback: ProgressCallback = None) -> None:
    """Export ``input_path`` to ``output_path`` in ``fmt`` (one of FORMATS)."""
    try:
        exporter = _EXPORTERS[fmt]
    except KeyError:
        raise ValueError(f"Unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")
    exporter(input_path, output_path, gauges=gauges, progress_callback=progress_callback)


def list_gauges(input_path: str) -> List[Tuple[str, int, int]]:
    """Return (gauge_id, interval_seconds, record_count) per gauge, file order."""
    rff = read_rff_header_and_directory(input_path)
    return [
        (e.gauge_id, e.interval_seconds, (e.end_offset - e.start_offset) // RECORD_SIZE)
        for e in rff.directory
    ]


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export gauge data from a SWMM5-RAIN .rff file to CSV, SWMM .dat, or JSON."
    )
    p.add_argument("input", help="Input .rff file")
    p.add_argument("-o", "--output", help="Output file path")
    p.add_argument(
        "-f", "--format", choices=FORMATS,
        help="Output format (default: inferred from the output extension, else csv)",
    )
    p.add_argument(
        "--gauges",
        help="Comma-separated gauge IDs to export (default: all gauges)",
    )
    p.add_argument(
        "--list", action="store_true",
        help="List gauges in the file (ID, interval, record count) and exit",
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 2

    if args.list:
        rows = list_gauges(str(input_path))
        print(f"{len(rows)} gauges in {input_path.name}:")
        for gid, interval, count in rows:
            print(f"  {gid:<16} interval={interval}s  records={count:,}")
        return 0

    if not args.output:
        print("ERROR: -o/--output is required unless --list is given", file=sys.stderr)
        return 2

    output_path = Path(args.output).expanduser().resolve()
    if not output_path.parent.exists():
        print(f"ERROR: Output directory does not exist: {output_path.parent}", file=sys.stderr)
        return 2

    fmt = args.format or EXTENSION_FORMATS.get(output_path.suffix.lower(), "csv")
    gauges = [g.strip() for g in args.gauges.split(",") if g.strip()] if args.gauges else None

    def progress(current: int, total: int, gid: str) -> None:
        if current == 1 or current % 25 == 0 or current == total:
            print(f"  Gauge {current}/{total}: {gid}")

    print(f"Exporting {input_path.name} -> {output_path.name} ({fmt})")
    export_rff_file(str(input_path), str(output_path), fmt,
                    gauges=gauges, progress_callback=progress)
    print(f"Done. Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
