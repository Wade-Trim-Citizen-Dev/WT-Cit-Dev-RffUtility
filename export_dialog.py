"""Export dialog: write gauge data from a loaded .rff file to CSV/.dat/JSON."""

import os
from pathlib import Path

from export_rff import export_rff_file, list_gauges

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QLineEdit, QListWidget,
                             QListWidgetItem, QFileDialog, QMessageBox,
                             QProgressBar, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# (label, format key, file-dialog filter, default extension)
_FORMAT_CHOICES = [
    ("CSV — one row per reading", "csv", "CSV Files (*.csv)", ".csv"),
    ("CSV — one column per gauge", "csv-wide", "CSV Files (*.csv)", ".csv"),
    ("CSV — one file per gauge", "csv-split", "CSV Files (*.csv)", ".csv"),
    ("SWMM rain data (.dat)", "dat", "SWMM Rain Data (*.dat *.txt)", ".dat"),
    ("JSON", "json", "JSON Files (*.json)", ".json"),
]


class ExportWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, input_path, output_path, fmt, gauges):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.fmt = fmt
        self.gauges = gauges

    def run(self):
        try:
            result = export_rff_file(
                self.input_path, self.output_path, self.fmt,
                gauges=self.gauges,
                progress_callback=lambda c, t, g: self.progress.emit(c, t, g),
            )
            if isinstance(result, list):
                self.finished.emit(f"{Path(self.output_path).parent} ({len(result)} files)")
            else:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ExportDialog(QDialog):
    def __init__(self, file_paths, parent=None, initial_path=None):
        super().__init__(parent)
        self.setWindowTitle("Export RFF Data")
        self.setMinimumSize(520, 540)
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Source & format --------------------------------------------------
        src_group = QGroupBox("Source && Format")
        src_layout = QVBoxLayout(src_group)
        src_layout.setSpacing(8)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File:"))
        self.file_combo = QComboBox()
        for path in file_paths:
            self.file_combo.addItem(Path(path).name, path)
            self.file_combo.setItemData(self.file_combo.count() - 1, path, Qt.ToolTipRole)
        if initial_path is not None and initial_path in file_paths:
            self.file_combo.setCurrentIndex(file_paths.index(initial_path))
        self.file_combo.currentIndexChanged.connect(self.load_gauge_list)
        file_row.addWidget(self.file_combo, stretch=1)
        src_layout.addLayout(file_row)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        for label, _, _, _ in _FORMAT_CHOICES:
            self.format_combo.addItem(label)
        self.format_combo.currentIndexChanged.connect(self.update_output_extension)
        fmt_row.addWidget(self.format_combo, stretch=1)
        src_layout.addLayout(fmt_row)
        layout.addWidget(src_group)

        # --- Gauge selection --------------------------------------------------
        gauge_group = QGroupBox("Gauges")
        gauge_layout = QVBoxLayout(gauge_group)
        gauge_layout.setSpacing(8)

        self.gauge_hint = QLabel("")
        self.gauge_hint.setObjectName("sectionHint")
        gauge_layout.addWidget(self.gauge_hint)

        self.gauge_list = QListWidget()
        gauge_layout.addWidget(self.gauge_list)

        check_row = QHBoxLayout()
        btn_all = QPushButton("Check All")
        btn_all.clicked.connect(lambda: self.set_all_checked(True))
        btn_none = QPushButton("Uncheck All")
        btn_none.clicked.connect(lambda: self.set_all_checked(False))
        check_row.addWidget(btn_all)
        check_row.addWidget(btn_none)
        check_row.addStretch()
        gauge_layout.addLayout(check_row)
        layout.addWidget(gauge_group, stretch=1)

        # --- Output -----------------------------------------------------------
        out_group = QGroupBox("Output File")
        out_layout = QVBoxLayout(out_group)
        out_layout.setSpacing(8)
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Choose where to save the exported file…")
        self.out_edit.textChanged.connect(self.update_output_hint)
        out_row.addWidget(self.out_edit)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self.browse_output)
        out_row.addWidget(btn_browse)
        out_layout.addLayout(out_row)
        self.out_hint = QLabel("")
        self.out_hint.setObjectName("sectionHint")
        self.out_hint.hide()
        out_layout.addWidget(self.out_hint)
        layout.addWidget(out_group)

        # --- Actions / progress -----------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.status_label, stretch=1)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)
        self.btn_export = QPushButton("Export")
        self.btn_export.setObjectName("mergeButton")
        self.btn_export.setMinimumWidth(120)
        self.btn_export.clicked.connect(self.start_export)
        btn_row.addWidget(self.btn_export)
        layout.addLayout(btn_row)

        self.load_gauge_list()

    # --- Helpers --------------------------------------------------------------
    def current_format(self):
        return _FORMAT_CHOICES[self.format_combo.currentIndex()]

    def load_gauge_list(self):
        self.gauge_list.clear()
        path = self.file_combo.currentData()
        if not path:
            return
        try:
            rows = list_gauges(path)
        except Exception as e:
            self.gauge_hint.setText(f"Could not read gauges: {e}")
            return
        empty = sum(1 for _, _, count in rows if count == 0)
        self.gauge_hint.setText(
            f"{len(rows)} gauges ({empty} without data). All checked gauges are exported."
        )
        for gid, interval, count in rows:
            item = QListWidgetItem(f"{gid}   ·   {interval}s interval   ·   {count:,} records")
            item.setData(Qt.UserRole, gid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.gauge_list.addItem(item)
        self.suggest_output_path()

    def set_all_checked(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.gauge_list.count()):
            self.gauge_list.item(i).setCheckState(state)

    def checked_gauges(self):
        gauges = []
        for i in range(self.gauge_list.count()):
            item = self.gauge_list.item(i)
            if item.checkState() == Qt.Checked:
                gauges.append(item.data(Qt.UserRole))
        return gauges

    def suggest_output_path(self):
        path = self.file_combo.currentData()
        if not path:
            return
        _, _, _, ext = self.current_format()
        self.out_edit.setText(str(Path(path).with_suffix(ext)))

    def update_output_extension(self):
        current = self.out_edit.text().strip()
        if not current:
            self.suggest_output_path()
        else:
            _, _, _, ext = self.current_format()
            self.out_edit.setText(str(Path(current).with_suffix(ext)))
        self.update_output_hint()

    def update_output_hint(self):
        _, fmt, _, _ = self.current_format()
        path = self.out_edit.text().strip()
        if fmt != "csv-split" or not path:
            self.out_hint.hide()
            return
        base = Path(path)
        self.out_hint.setText(
            f"One file per gauge: {base.stem}_<gauge>{base.suffix or '.csv'}"
        )
        self.out_hint.show()

    def browse_output(self):
        _, _, file_filter, ext = self.current_format()
        start = self.out_edit.text().strip() or str(
            Path(self.file_combo.currentData() or "").with_suffix(ext)
        )
        file, _ = QFileDialog.getSaveFileName(self, "Save Exported File", start, file_filter)
        if file:
            self.out_edit.setText(file)

    # --- Export ----------------------------------------------------------------
    def start_export(self):
        input_path = self.file_combo.currentData()
        output_path = self.out_edit.text().strip()
        gauges = self.checked_gauges()

        if not input_path:
            QMessageBox.warning(self, "Error", "No source file selected.")
            return
        if not output_path:
            QMessageBox.warning(self, "Error", "No output file selected.")
            return
        if not gauges:
            QMessageBox.warning(self, "Error", "No gauges checked for export.")
            return
        if os.path.normcase(os.path.abspath(output_path)) == os.path.normcase(os.path.abspath(input_path)):
            QMessageBox.warning(self, "Error", "Output file must differ from the input file.")
            return

        # Exporting every gauge? Skip the filter so new gauges never error.
        if len(gauges) == self.gauge_list.count():
            gauges = None

        _, fmt, _, _ = self.current_format()

        self.btn_export.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("Exporting…")

        self.worker = ExportWorker(input_path, output_path, fmt, gauges)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.export_finished)
        self.worker.error.connect(self.export_error)
        self.worker.start()

    def update_progress(self, current, total, gid):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Exporting gauge: {gid} ({current}/{total})")

    def export_finished(self, output_path):
        self.btn_export.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("Export completed.")
        QMessageBox.information(self, "Success", f"Data exported to:\n{output_path}")

    def export_error(self, err_msg):
        self.btn_export.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("Export failed.")
        QMessageBox.critical(self, "Error", f"An error occurred during export:\n{err_msg}")
