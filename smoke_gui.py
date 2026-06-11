"""Offscreen GUI smoke test: instantiate the main window and both dialogs
against the real example files, exercise the control paths, and exit non-zero
on any Qt/runtime error. Not part of the unit test suite (needs PyQt5)."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

# Modal message boxes can't be dismissed offscreen — record and swallow them.
boxes = []
for name in ("information", "warning", "critical"):
    setattr(QMessageBox, name,
            staticmethod(lambda *a, _n=name, **k: boxes.append((_n, a[1:3])) or QMessageBox.Ok))

import main as app_main
from export_dialog import ExportDialog
from visualize import VisualizationDialog

EXAMPLES = [
    os.path.join("examples", "Q2_2018_Rainfall.rff"),
    os.path.join("examples", "Q3_2018_Rainfall.rff"),
]

failures = []

app = QApplication(sys.argv)
window = app_main.MainWindow()
for p in EXAMPLES:
    window.file_list.add_file(os.path.abspath(p))
assert window.file_list.count() == 2, "file list should hold both examples"
assert window.logo_label.pixmap() and not window.logo_label.pixmap().isNull(), \
    "header logo should load from assets/logo.png"

# --- ExportDialog ---------------------------------------------------------
dlg = ExportDialog(window.get_file_paths(), parent=window,
                   initial_path=window.get_file_paths()[1])
assert dlg.file_combo.currentIndex() == 1, "initial_path should preselect file"
assert dlg.gauge_list.count() == 1245, f"expected 1245 gauges, got {dlg.gauge_list.count()}"
assert dlg.out_edit.text().endswith(".csv"), "suggested output should be .csv"
dlg.format_combo.setCurrentText("SWMM rain data (.dat)")
assert dlg.out_edit.text().endswith(".dat"), "extension should follow format"
dlg.set_all_checked(False)
dlg.gauge_list.item(0).setCheckState(Qt.Checked)
out_path = os.path.join(os.environ["TEMP"], "smoke_export.dat")
dlg.out_edit.setText(out_path)
dlg.start_export()
dlg.worker.wait(30000)
app.processEvents()
assert os.path.getsize(out_path) > 0, "export should write data"
with open(out_path, encoding="utf-8") as f:
    first = f.readline().split()
assert len(first) == 7, f"dat line should have 7 fields, got {first}"
print("ExportDialog OK:", first)

# csv-split: one file per gauge, output path is the base name
dlg.format_combo.setCurrentText("CSV — one file per gauge")
split_base = os.path.join(os.environ["TEMP"], "smoke_split.csv")
dlg.out_edit.setText(split_base)
assert not dlg.out_hint.isHidden(), "csv-split should show the per-gauge name hint"
gid = dlg.gauge_list.item(0).data(Qt.UserRole)
dlg.start_export()
dlg.worker.wait(30000)
app.processEvents()
split_path = os.path.join(os.environ["TEMP"], f"smoke_split_{gid}.csv")
assert os.path.isfile(split_path), f"csv-split should write {split_path}"
with open(split_path, encoding="utf-8") as f:
    assert f.readline().strip() == "datetime,value", "split file should have datetime,value header"
print("ExportDialog csv-split OK:", os.path.basename(split_path))
dlg.close()

# --- VisualizationDialog ----------------------------------------------------
viz = VisualizationDialog(window.get_file_paths(), parent=window)
viz.thread.wait(60000)
app.processEvents()
assert viz.gauge_combo.count() > 0, "gauge combo should populate after analysis"
assert viz.table.rowCount() == 8, "stats table should have 8 rows"
viz.cumulative_check.setChecked(True)
app.processEvents()
viz.file_combo.setCurrentIndex(1)  # triggers PlotLoaderThread
viz.plot_loader.wait(60000)
app.processEvents()
assert viz.file_combo.isEnabled(), "file combo should re-enable after load"
assert viz.gauge_combo.count() > 0, "gauges should populate for second file"
vm = viz.values_model
gid = viz.gauge_combo.currentText()
assert vm.rowCount() == viz.plot_data_map[gid][0].size, \
    "values table should hold every record of the selected gauge"
assert vm.columnCount() == 3, "values table should have datetime/value/cumulative"
row0 = [vm.index(0, c).data() for c in range(3)]
assert row0[0].startswith("2018-"), f"first cell should be a 2018 datetime, got {row0[0]}"
assert row0[1] == row0[2], "first cumulative value should equal the first value"
print("Values table OK:", vm.rowCount(), "rows, first row:", row0)
print("VisualizationDialog OK:",
      viz.table.item(4, 1).text(), "points,", viz.gauge_combo.count(), "plottable gauges")
viz.close()

window.close()
QTimer.singleShot(0, app.quit)
app.exec_()
errors = [b for b in boxes if b[0] == "critical"]
assert not errors, f"error dialogs were shown: {errors}"
print("Message boxes shown:", [b[0] for b in boxes])
print("SMOKE TEST PASSED")
