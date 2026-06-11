import sys
import os
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
                             QAbstractItemView, QFileDialog, QLabel, QLineEdit,
                             QMessageBox, QProgressBar, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPainter, QColor

from merge_rff import merge_rff
from visualize import VisualizationDialog
from export_dialog import ExportDialog
from theme import STYLESHEET, PLACEHOLDER

VERSION = "v2.1.0"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class MergeThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, input_paths, output_path):
        super().__init__()
        self.input_paths = input_paths
        self.output_path = output_path

    def run(self):
        try:
            def merge_callback(current, total, gid):
                self.progress.emit(current, total, gid)
                
            merge_rff(
                input_paths=self.input_paths,
                output_path=self.output_path,
                progress_every=1,
                progress_callback=merge_callback
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class DragDropListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = str(url.toLocalFile())
                    if file_path.lower().endswith('.rff'):
                        self.add_file(file_path)
        else:
            super().dropEvent(event)

    def add_file(self, file_path):
        # Prevent duplicates
        for i in range(self.count()):
            if self.item(i).data(Qt.UserRole) == file_path:
                return
        item = QListWidgetItem(Path(file_path).name)
        item.setData(Qt.UserRole, file_path)
        item.setToolTip(file_path)
        self.addItem(item)

    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw a centered hint while the list is empty.
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.save()
            painter.setPen(QColor(PLACEHOLDER))
            painter.drawText(
                self.viewport().rect(),
                Qt.AlignCenter,
                "Drag & drop .rff files here\nor click “Add Files”",
            )
            painter.restore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"RFF Utilities {VERSION}")
        self.setWindowIcon(QIcon(resource_path(os.path.join("assets", "icon.ico"))))
        self.setMinimumSize(640, 620)
        self.resize(680, 660)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 16)
        main_layout.setSpacing(14)

        # --- Header ---------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(
            QIcon(resource_path(os.path.join("assets", "icon.ico"))).pixmap(QSize(44, 44))
        )
        icon_label.setFixedSize(44, 44)
        header.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("RFF Utilities")
        title.setObjectName("title")
        subtitle = QLabel("Read, visualize, export & merge SWMM5-RAIN rainfall files")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        header_right = QVBoxLayout()
        header_right.setSpacing(4)
        version_label = QLabel(VERSION)
        version_label.setObjectName("subtitle")
        version_label.setAlignment(Qt.AlignRight)
        header_right.addWidget(version_label)
        btn_help = QPushButton("Help")
        btn_help.clicked.connect(self.show_help)
        header_right.addWidget(btn_help)
        header.addLayout(header_right)
        main_layout.addLayout(header)

        # --- Files ------------------------------------------------------------
        input_group = QGroupBox("RFF Files")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(8)

        hint = QLabel("Every tool below works on the files in this list.")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        input_layout.addWidget(hint)

        self.file_list = DragDropListWidget()
        input_layout.addWidget(self.file_list)

        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(8)
        btn_add = QPushButton("Add Files")
        btn_add.clicked.connect(self.browse_input_files)
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.remove_selected_files)
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self.file_list.clear)
        list_btn_layout.addWidget(btn_add)
        list_btn_layout.addWidget(btn_remove)
        list_btn_layout.addWidget(btn_clear)
        list_btn_layout.addStretch()
        input_layout.addLayout(list_btn_layout)
        main_layout.addWidget(input_group)

        # --- Inspect & convert --------------------------------------------------
        inspect_group = QGroupBox("Inspect && Convert")
        inspect_layout = QVBoxLayout(inspect_group)
        inspect_layout.setSpacing(8)

        inspect_hint = QLabel("Browse per-gauge statistics and rainfall plots, or "
                              "convert files to CSV, SWMM rain data (.dat), or JSON.")
        inspect_hint.setObjectName("sectionHint")
        inspect_hint.setWordWrap(True)
        inspect_layout.addWidget(inspect_hint)

        inspect_btns = QHBoxLayout()
        inspect_btns.setSpacing(8)
        btn_visualize = QPushButton("Visualize / Statistics")
        btn_visualize.clicked.connect(self.show_visualization)
        inspect_btns.addWidget(btn_visualize)
        btn_export = QPushButton("Export…")
        btn_export.clicked.connect(self.show_export)
        inspect_btns.addWidget(btn_export)
        inspect_btns.addStretch()
        inspect_layout.addLayout(inspect_btns)
        main_layout.addWidget(inspect_group)

        # --- Merge --------------------------------------------------------------
        merge_group = QGroupBox("Merge")
        merge_layout = QVBoxLayout(merge_group)
        merge_layout.setSpacing(8)

        merge_hint = QLabel("Combines every listed file into one .rff. Drag to "
                            "reorder — files lower in the list overwrite higher "
                            "ones on overlapping timestamps.")
        merge_hint.setObjectName("sectionHint")
        merge_hint.setWordWrap(True)
        merge_layout.addWidget(merge_hint)

        merge_row = QHBoxLayout()
        merge_row.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Choose where to save the merged .rff file…")
        merge_row.addWidget(self.out_edit)
        btn_out_browse = QPushButton("Browse…")
        btn_out_browse.clicked.connect(self.browse_output_file)
        merge_row.addWidget(btn_out_browse)
        self.btn_merge = QPushButton("Merge Files")
        self.btn_merge.setObjectName("mergeButton")
        self.btn_merge.setMinimumWidth(130)
        self.btn_merge.clicked.connect(self.start_merge)
        merge_row.addWidget(self.btn_merge)
        merge_layout.addLayout(merge_row)
        main_layout.addWidget(merge_group)

        # --- Progress / status ---------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        main_layout.addWidget(self.status_label)

    def get_file_paths(self):
        paths = []
        for i in range(self.file_list.count()):
            paths.append(self.file_list.item(i).data(Qt.UserRole))
        return paths

    def browse_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select RFF Files", "", "RFF Files (*.rff)")
        for f in files:
            self.file_list.add_file(f)

    def remove_selected_files(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def browse_output_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Merged RFF", "", "RFF Files (*.rff)")
        if file:
            self.out_edit.setText(file)

    def show_visualization(self):
        paths = self.get_file_paths()
        if not paths:
            QMessageBox.warning(self, "No files", "Please add at least one .rff file to visualize.")
            return
        
        dlg = VisualizationDialog(paths, self)
        dlg.exec_()

    def show_export(self):
        paths = self.get_file_paths()
        if not paths:
            QMessageBox.warning(self, "No files", "Please add at least one .rff file to export.")
            return

        selected = self.file_list.selectedItems()
        initial = selected[0].data(Qt.UserRole) if selected else None
        dlg = ExportDialog(paths, parent=self, initial_path=initial)
        dlg.exec_()

    def show_help(self):
        msg = (
            f"RFF Utilities {VERSION}\n\n"
            "Tools for SWMM5-RAIN .rff binary rainfall files: read, visualize, "
            "export, and merge.\n\n"
            "Files\n"
            "- Drag .rff files into the list (or click 'Add Files'). Every tool "
            "works on the files in this list.\n\n"
            "Visualize / Statistics\n"
            "- Per-gauge statistics across all listed files, plus an interactive "
            "rainfall plot with a per-file gauge browser and a cumulative view.\n\n"
            "Export\n"
            "- Convert a file to CSV (one row per reading, one column per gauge, "
            "or one file per gauge), SWMM rain data (.dat), or JSON — all gauges "
            "or a checked subset.\n\n"
            "Merge\n"
            "- Combine every listed file into one .rff. Drag to reorder: files "
            "lower in the list overwrite higher ones on overlapping timestamps.\n\n"
            "Credits: Ross Volkwein"
        )
        QMessageBox.information(self, "Help & About", msg)

    def start_merge(self):
        input_paths = self.get_file_paths()
        output_path = self.out_edit.text()

        if not input_paths:
            QMessageBox.warning(self, "Error", "No input files selected.")
            return
        if not output_path:
            QMessageBox.warning(self, "Error", "No output file selected.")
            return

        # Disable UI
        self.btn_merge.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("Merging...")

        self.thread = MergeThread(input_paths, output_path)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.merge_finished)
        self.thread.error.connect(self.merge_error)
        self.thread.start()

    def update_progress(self, current, total, gid):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing Gauge: {gid} ({current}/{total})")

    def merge_finished(self):
        self.btn_merge.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("Merge completed successfully!")
        QMessageBox.information(self, "Success", f"Files merged successfully into:\n{self.out_edit.text()}")

    def merge_error(self, err_msg):
        self.btn_merge.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("Merge failed.")
        QMessageBox.critical(self, "Error", f"An error occurred during merging:\n{err_msg}")


def main():
    app = QApplication(sys.argv)

    # Styling
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(resource_path(os.path.join("assets", "icon.ico"))))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
