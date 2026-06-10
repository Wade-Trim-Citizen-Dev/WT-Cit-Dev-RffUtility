import sys
from pathlib import Path

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QCheckBox, QProgressBar)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import numpy as np
import pyqtgraph as pg

from merge_rff import (excel_to_datetime, read_rff_header_and_directory,
                       read_gauge_arrays)
from export_dialog import ExportDialog
from theme import ACCENT, SURFACE, TEXT

# Global pyqtgraph look: white canvas, dark axes, smooth lines.
pg.setConfigOption("background", SURFACE)
pg.setConfigOption("foreground", TEXT)
pg.setConfigOptions(antialias=True)


class DataProcessorThread(QThread):
    progress = pyqtSignal(int, int, str)  # current, total, label
    finished = pyqtSignal(dict, list) # stats, plot_data
    error = pyqtSignal(str)

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        try:
            stats = {
                "file_count": len(self.file_paths),
                "gauge_count": 0,
                "active_gauges": 0,
                "empty_gauges_list": [],
                "total_points": 0,
                "min_date": float('inf'),
                "max_date": float('-inf'),
                "max_rain": 0.0
            }
            plot_data = [] # List of (times, values, gauge_id) arrays for first file

            if not self.file_paths:
                self.finished.emit(stats, plot_data)
                return

            # Headers first, so progress can count gauges across all files
            rffs = [read_rff_header_and_directory(p) for p in self.file_paths]
            stats["gauge_count"] = rffs[0].gauge_count
            total_gauges = sum(r.gauge_count for r in rffs)

            all_gauges = set(entry.gauge_id for entry in rffs[0].directory)
            gauges_with_data = set()

            # Process all files for stats, one open handle per file
            done = 0
            for path, rff in zip(self.file_paths, rffs):
                name = Path(path).name
                with open(path, "rb") as fh:
                    for entry in rff.directory:
                        done += 1
                        self.progress.emit(done, total_gauges, name)
                        times, values = read_gauge_arrays(path, entry, fh=fh)
                        stats["total_points"] += times.size
                        if times.size:
                            gauges_with_data.add(entry.gauge_id)

                            stats["min_date"] = min(stats["min_date"], float(times.min()))
                            stats["max_date"] = max(stats["max_date"], float(times.max()))
                            stats["max_rain"] = max(stats["max_rain"], float(values.max()))

                            # Grab the first file's gauges for plotting to keep it light
                            if path == self.file_paths[0]:
                                plot_data.append((times, values, entry.gauge_id))

            empty_gauges = all_gauges - gauges_with_data
            stats["active_gauges"] = len(gauges_with_data)
            stats["empty_gauges_list"] = sorted(list(empty_gauges))

            self.finished.emit(stats, plot_data)
        except Exception as e:
            self.error.emit(str(e))


class PlotLoaderThread(QThread):
    """Load (times, values, gauge_id) arrays for one file, for plotting."""
    progress = pyqtSignal(int, int, str)  # current, total, label
    finished = pyqtSignal(str, list)  # path, plot_data
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            plot_data = []
            rff = read_rff_header_and_directory(self.path)
            name = Path(self.path).name
            with open(self.path, "rb") as fh:
                for i, entry in enumerate(rff.directory):
                    self.progress.emit(i + 1, rff.gauge_count, name)
                    times, values = read_gauge_arrays(self.path, entry, fh=fh)
                    if times.size:
                        plot_data.append((times, values, entry.gauge_id))
            self.finished.emit(self.path, plot_data)
        except Exception as e:
            self.error.emit(str(e))


class VisualizationDialog(QDialog):
    def __init__(self, file_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Statistics & Visualization")
        self.resize(800, 640)
        self.file_paths = file_paths
        self.plot_data_map = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.info_label = QLabel("Analyzing data…")
        self.info_label.setObjectName("subtitle")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(0, 0)  # indeterminate until first progress signal
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Statistic", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        # Plot controls: file + gauge selectors, cumulative toggle
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("File:"))
        self.file_combo = QComboBox()
        for path in file_paths:
            self.file_combo.addItem(Path(path).name, path)
            self.file_combo.setItemData(self.file_combo.count() - 1, path, Qt.ToolTipRole)
        self.file_combo.currentIndexChanged.connect(self.on_file_selected)
        selector_layout.addWidget(self.file_combo)

        selector_layout.addWidget(QLabel("Gauge:"))
        self.gauge_combo = QComboBox()
        self.gauge_combo.currentIndexChanged.connect(self.on_gauge_selected)
        selector_layout.addWidget(self.gauge_combo)

        self.cumulative_check = QCheckBox("Cumulative")
        self.cumulative_check.toggled.connect(self.replot_current_gauge)
        selector_layout.addWidget(self.cumulative_check)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        axis = pg.DateAxisItem(orientation='bottom')
        self.plot_widget = pg.PlotWidget(title="Rainfall Data Preview", axisItems={'bottom': axis})
        self.plot_widget.setLabel('left', 'Rainfall', units='in/mm')
        self.plot_widget.setLabel('bottom', 'Time (Date)')
        self.plot_widget.showGrid(x=True, y=True)
        layout.addWidget(self.plot_widget)

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export…")
        export_btn.clicked.connect(self.show_export)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Start thread
        self.thread = DataProcessorThread(file_paths)
        self.thread.progress.connect(self.on_progress)
        self.thread.finished.connect(self.on_processing_finished)
        self.thread.error.connect(self.on_processing_error)
        self.thread.start()

    def on_progress(self, current, total, name):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.info_label.setText(f"Reading {name} — gauge {current}/{total}")

    def on_processing_finished(self, stats, plot_data):
        self.progress_bar.hide()
        self.info_label.setText(f"Analysis complete for {stats['file_count']} files.")

        # Populate table
        stat_rows = []
        if stats['total_points'] > 0:
            min_dt = excel_to_datetime(stats['min_date']).strftime("%Y-%m-%d %H:%M:%S")
            max_dt = excel_to_datetime(stats['max_date']).strftime("%Y-%m-%d %H:%M:%S")

            empty_text = ", ".join(stats['empty_gauges_list']) if stats['empty_gauges_list'] else "None"

            stat_rows = [
                ("Total Files", str(stats['file_count'])),
                ("Expected Gauges", str(stats['gauge_count'])),
                ("Gauges with Data", f"{stats['active_gauges']} ({stats['gauge_count'] - stats['active_gauges']} empty)"),
                ("Empty Gauges List", empty_text),
                ("Total Data Points", f"{stats['total_points']:,}"),
                ("Start Date", min_dt),
                ("End Date", max_dt),
                ("Max Rainfall", f"{stats['max_rain']:.4f}")
            ]
        else:
            stat_rows = [("Error", "No data points found")]

        self.table.setRowCount(len(stat_rows))
        for row, (k, v) in enumerate(stat_rows):
            self.table.setItem(row, 0, QTableWidgetItem(k))
            self.table.setItem(row, 1, QTableWidgetItem(v))
        self.table.resizeRowsToContents()

        self.set_plot_data(plot_data)

    def set_plot_data(self, plot_data):
        self.plot_data_map = {gid: (times, values) for times, values, gid in plot_data}

        self.gauge_combo.blockSignals(True)
        self.gauge_combo.clear()
        self.gauge_combo.addItems(list(self.plot_data_map.keys()))
        self.gauge_combo.blockSignals(False)

        if self.gauge_combo.count() > 0:
            self.on_gauge_selected(0)
        else:
            self.plot_widget.clear()
            self.plot_widget.setTitle("Rainfall Data Preview — no data in this file")

    def on_file_selected(self, index):
        if index < 0:
            return
        path = self.file_combo.currentData()
        # Block re-entry while loading; combo is re-enabled when the load ends.
        self.file_combo.setEnabled(False)
        self.info_label.setText(f"Loading {Path(path).name}…")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.plot_loader = PlotLoaderThread(path)
        self.plot_loader.progress.connect(self.on_progress)
        self.plot_loader.finished.connect(self.on_plot_loaded)
        self.plot_loader.error.connect(self.on_plot_load_error)
        self.plot_loader.start()

    def on_plot_loaded(self, path, plot_data):
        self.file_combo.setEnabled(True)
        self.progress_bar.hide()
        self.info_label.setText(f"Analysis complete for {len(self.file_paths)} files.")
        self.set_plot_data(plot_data)

    def on_plot_load_error(self, err_msg):
        self.file_combo.setEnabled(True)
        self.progress_bar.hide()
        self.info_label.setText(f"Error loading file: {err_msg}")

    def on_gauge_selected(self, index):
        if index < 0:
            return
        self.replot_current_gauge()

    def replot_current_gauge(self):
        gid = self.gauge_combo.currentText()
        if gid not in self.plot_data_map:
            return
        times, values = self.plot_data_map[gid]
        unix_times = (times - 25569.0) * 86400.0
        cumulative = self.cumulative_check.isChecked()
        plot_values = np.cumsum(values, dtype=np.float64) if cumulative else values

        self.plot_widget.clear()
        accent = pg.mkColor(ACCENT)
        fill = pg.mkColor(ACCENT)
        fill.setAlpha(50)
        self.plot_widget.plot(
            unix_times,
            plot_values,
            pen=pg.mkPen(accent, width=1.5),
            fillLevel=0,
            brush=fill,
            name=gid,
        )
        self.plot_widget.setLabel('left', 'Cumulative Rainfall' if cumulative else 'Rainfall',
                                  units='in/mm')
        kind = "Cumulative Rainfall" if cumulative else "Rainfall Data"
        self.plot_widget.setTitle(f"{kind} Preview — Gauge: {gid}")

    def show_export(self):
        dlg = ExportDialog(self.file_paths, parent=self,
                           initial_path=self.file_combo.currentData())
        dlg.exec_()

    def on_processing_error(self, err_msg):
        self.progress_bar.hide()
        self.info_label.setText(f"Error analyzing data: {err_msg}")
