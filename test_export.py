import json
import struct
import tempfile
import unittest
from pathlib import Path

from merge_rff import (GAUGE_BLOCK_SIZE, GAUGE_ID_SIZE, MAGIC,
                       excel_to_datetime, read_gauge_arrays,
                       read_gauge_records, read_rff_header_and_directory)
from export_rff import (excel_to_rounded_datetime, export_rff_file,
                        format_value, list_gauges)

# 2018-04-01 00:00 as an Excel day serial (origin 1899-12-30)
T0 = 43191.0
STEP = 900.0 / 86400.0  # 15 minutes in days


def write_rff(path, gauges, interval_seconds=900):
    """Write a minimal SWMM5-RAIN file. ``gauges`` is [(gauge_id, records)]."""
    header_size = len(MAGIC) + 4 + len(gauges) * GAUGE_BLOCK_SIZE
    blobs = []
    offset = header_size
    blocks = []
    for gid, records in gauges:
        blob = b"".join(struct.pack("<df", t, v) for t, v in records)
        start, end = offset, offset + len(blob)
        offset = end
        blobs.append(blob)
        block = (gid.encode("ascii").ljust(GAUGE_ID_SIZE, b"\x00")
                 + b"\x00" * (GAUGE_BLOCK_SIZE - GAUGE_ID_SIZE - 16)
                 + struct.pack("<IIII", 0, interval_seconds, start, end))
        blocks.append(block)

    with open(path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", len(gauges)))
        for block in blocks:
            f.write(block)
        for blob in blobs:
            f.write(blob)


class TestExportRFF(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.rff_path = str(self.dir / "test.rff")
        write_rff(self.rff_path, [
            ("G1", [(T0, 0.5), (T0 + STEP, 0.25)]),
            ("G2", [(T0 + STEP, 1.5)]),
            ("EMPTY", []),
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def export(self, fmt, name, gauges=None):
        out = str(self.dir / name)
        export_rff_file(self.rff_path, out, fmt, gauges=gauges)
        return Path(out).read_text(encoding="utf-8")

    def test_time_conversion(self):
        self.assertEqual(excel_to_datetime(T0).strftime("%Y-%m-%d %H:%M:%S"),
                         "2018-04-01 00:00:00")
        # Rounding kills float64 jitter near interval boundaries
        jitter = T0 + STEP - 1e-9
        self.assertEqual(excel_to_rounded_datetime(jitter).strftime("%H:%M:%S"),
                         "00:15:00")

    def test_format_value(self):
        # float32 round trip of 0.25 is exact; 0.1 is not — %.6g cleans it up
        self.assertEqual(format_value(0.25), "0.25")
        f32_tenth = struct.unpack("<f", struct.pack("<f", 0.1))[0]
        self.assertEqual(format_value(f32_tenth), "0.1")

    def test_read_gauge_arrays_matches_records(self):
        rff = read_rff_header_and_directory(self.rff_path)
        for entry in rff.directory:
            recs = read_gauge_records(self.rff_path, entry)
            times, values = read_gauge_arrays(self.rff_path, entry)
            self.assertEqual(str(times.dtype), "float64")
            self.assertEqual(str(values.dtype), "float32")
            self.assertEqual(times.size, len(recs))
            for (t, v), at, av in zip(recs, times, values):
                self.assertEqual(t, at)
                self.assertEqual(v, av)

    def test_list_gauges(self):
        rows = list_gauges(self.rff_path)
        self.assertEqual(rows, [("G1", 900, 2), ("G2", 900, 1), ("EMPTY", 900, 0)])

    def test_export_csv(self):
        lines = self.export("csv", "out.csv").splitlines()
        self.assertEqual(lines[0], "gauge_id,datetime,value")
        self.assertEqual(lines[1], "G1,2018-04-01 00:00:00,0.5")
        self.assertEqual(lines[2], "G1,2018-04-01 00:15:00,0.25")
        self.assertEqual(lines[3], "G2,2018-04-01 00:15:00,1.5")
        self.assertEqual(len(lines), 4)  # EMPTY contributes no rows

    def test_export_csv_wide(self):
        lines = self.export("csv-wide", "out_wide.csv").splitlines()
        self.assertEqual(lines[0], "datetime,G1,G2,EMPTY")
        self.assertEqual(lines[1], "2018-04-01 00:00:00,0.5,,")
        self.assertEqual(lines[2], "2018-04-01 00:15:00,0.25,1.5,")
        self.assertEqual(len(lines), 3)

    def test_export_dat(self):
        lines = self.export("dat", "out.dat").splitlines()
        self.assertEqual(lines[0], "G1 2018 04 01 00 00 0.5")
        self.assertEqual(lines[1], "G1 2018 04 01 00 15 0.25")
        self.assertEqual(lines[2], "G2 2018 04 01 00 15 1.5")
        self.assertEqual(len(lines), 3)

    def test_export_json(self):
        data = json.loads(self.export("json", "out.json"))
        self.assertEqual(data["source"], "test.rff")
        self.assertEqual([g["id"] for g in data["gauges"]], ["G1", "G2", "EMPTY"])
        g1 = data["gauges"][0]
        self.assertEqual(g1["interval_seconds"], 900)
        self.assertEqual(g1["record_count"], 2)
        self.assertEqual(g1["records"][0], ["2018-04-01 00:00:00", 0.5])
        self.assertEqual(data["gauges"][2]["records"], [])

    def test_gauge_filter(self):
        lines = self.export("csv", "g2.csv", gauges=["G2"]).splitlines()
        self.assertEqual(lines[1:], ["G2,2018-04-01 00:15:00,1.5"])

    def test_unknown_gauge_raises(self):
        with self.assertRaises(ValueError):
            self.export("csv", "bad.csv", gauges=["NOPE"])

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            export_rff_file(self.rff_path, str(self.dir / "x.xyz"), "xyz")


if __name__ == "__main__":
    unittest.main()
