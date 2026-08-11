from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .exif import Photo, discover_photos, load_photo, read_taken_at, write_gps_tags
from .gpx import TrackPoint, interpolate, parse_gpx
from .timeutil import format_offset, parse_actual_date_time


@dataclass(frozen=True)
class Match:
    photo: Photo
    adjusted_time_utc: datetime
    point: TrackPoint | None
    status: str


class PhotoViewerDialog(QDialog):
    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(path.name)
        self.resize(1000, 760)
        self._zoom = 0

        pixmap = QPixmap(str(path))
        self.scene = QGraphicsScene(self)
        self.item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.item)

        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        zoom_in = QPushButton("Zoom In")
        zoom_in.clicked.connect(self.zoom_in)
        zoom_out = QPushButton("Zoom Out")
        zoom_out.clicked.connect(self.zoom_out)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset_zoom)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        controls = QHBoxLayout()
        controls.addWidget(zoom_out)
        controls.addWidget(zoom_in)
        controls.addWidget(reset)
        controls.addStretch()
        controls.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        layout.addLayout(controls)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._zoom == 0:
            self.view.fitInView(self.item, Qt.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self) -> None:
        self._apply_zoom(1.25, 1)

    def zoom_out(self) -> None:
        self._apply_zoom(0.8, -1)

    def reset_zoom(self) -> None:
        self._zoom = 0
        self.view.resetTransform()
        self.view.fitInView(self.item, Qt.KeepAspectRatio)

    def _apply_zoom(self, factor: float, step: int) -> None:
        next_zoom = self._zoom + step
        if next_zoom < -8 or next_zoom > 20:
            return
        self._zoom = next_zoom
        self.view.scale(factor, factor)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Time Offset Geotagger")
        self.resize(980, 680)

        self.gpx_points: list[TrackPoint] = []
        self.gpx_files: dict[Path, list[TrackPoint]] = {}
        self.matches: list[Match] = []

        self.gpx_list = QListWidget()
        self.gpx_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.gpx_list.setAlternatingRowColors(True)
        self.gpx_list.setMinimumHeight(88)
        self.photo_folder = QLineEdit()
        self.photo_folder.setReadOnly(True)
        self.calibration_photo = QLineEdit()
        self.calibration_photo.setReadOnly(True)
        self.actual_date = QDateEdit()
        self.actual_date.setCalendarPopup(True)
        self.actual_date.setDisplayFormat("yyyy-MM-dd")
        self.actual_date.setDate(QDate.currentDate())
        self.actual_clock_time = QTimeEdit()
        self.actual_clock_time.setDisplayFormat("HH:mm:ss")
        self.actual_clock_time.setTime(QTime.currentTime())
        self.actual_timezone = QLineEdit(self._default_timezone_text())
        self.actual_timezone.setPlaceholderText("+01:00 or Z")
        self.offset_seconds = QSpinBox()
        self.offset_seconds.setRange(-7 * 24 * 3600, 7 * 24 * 3600)
        self.offset_seconds.setSuffix(" s")
        self.offset_label = QLabel("+00:00:00")
        self.status_label = QLabel("Choose GPX files and a photo folder to begin.")

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Photo", "Camera time", "Track time UTC", "Latitude", "Longitude", "Altitude", "Status"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)

        self._build_ui()
        self.offset_seconds.valueChanged.connect(self._offset_changed)
        self._offset_changed()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        inputs = QGroupBox("Inputs")
        input_layout = QGridLayout(inputs)
        input_layout.addWidget(QLabel("GPX files"), 0, 0, Qt.AlignTop)
        input_layout.addWidget(self.gpx_list, 0, 1)
        gpx_buttons = QVBoxLayout()
        gpx_buttons.addWidget(self._button("Add", self.choose_gpx))
        gpx_buttons.addWidget(self._button("Remove", self.remove_selected_gpx))
        gpx_buttons.addStretch()
        input_layout.addLayout(gpx_buttons, 0, 2)
        input_layout.addWidget(QLabel("Photo folder"), 1, 0)
        input_layout.addWidget(self.photo_folder, 1, 1)
        input_layout.addWidget(self._button("Choose", self.choose_folder), 1, 2)
        input_layout.setRowStretch(0, 1)

        calibration = QGroupBox("Clock Calibration")
        calibration_layout = QGridLayout(calibration)
        calibration_layout.addWidget(QLabel("Calibration photo"), 0, 0)
        calibration_layout.addWidget(self.calibration_photo, 0, 1)
        calibration_buttons = QHBoxLayout()
        calibration_buttons.addWidget(self._button("Choose", self.choose_calibration_photo))
        calibration_buttons.addWidget(self._button("View", self.show_calibration_photo))
        calibration_layout.addLayout(calibration_buttons, 0, 2)
        calibration_layout.addWidget(QLabel("Actual phone date"), 1, 0)
        calibration_layout.addWidget(self.actual_date, 1, 1)
        calibration_layout.addWidget(QLabel("Actual phone time"), 2, 0)
        time_layout = QHBoxLayout()
        time_layout.addWidget(self.actual_clock_time)
        time_layout.addWidget(QLabel("Timezone"))
        time_layout.addWidget(self.actual_timezone)
        calibration_layout.addLayout(time_layout, 2, 1)
        calibration_layout.addWidget(self._button("Compute Offset", self.compute_offset), 2, 2)
        calibration_layout.addWidget(QLabel("Manual offset"), 3, 0)
        calibration_layout.addWidget(self.offset_seconds, 3, 1)
        calibration_layout.addWidget(self.offset_label, 3, 2)

        actions = QHBoxLayout()
        actions.addWidget(self._button("Preview Matches", self.preview_matches))
        actions.addWidget(self._button("Write GPS Tags", self.write_tags))
        actions.addStretch()

        root.addWidget(inputs)
        root.addWidget(calibration)
        root.addLayout(actions)
        root.addWidget(self.table, 1)
        root.addWidget(self.status_label)
        self.setCentralWidget(central)

    def _button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def choose_gpx(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(self, "Choose GPX files", "", "GPX files (*.gpx *.GPX)")
        if not filenames:
            return

        loaded = 0
        skipped = 0
        failures: list[str] = []
        for filename in filenames:
            path = Path(filename)
            if path in self.gpx_files:
                skipped += 1
                continue
            try:
                self.gpx_files[path] = parse_gpx(path)
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")
                continue
            loaded += 1

        self._refresh_gpx_list()
        if failures:
            self._error("Some GPX files could not be read", "\n".join(failures[:10]))
            return

        self.status_label.setText(self._gpx_status_text(loaded=loaded, skipped=skipped))

    def remove_selected_gpx(self) -> None:
        selected = self.gpx_list.selectedItems()
        if not selected:
            self.status_label.setText("Select one or more GPX files to remove.")
            return

        for item in selected:
            self.gpx_files.pop(Path(item.data(Qt.UserRole)), None)

        self._refresh_gpx_list()
        self.status_label.setText(self._gpx_status_text(removed=len(selected)))

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose photo folder")
        if not folder:
            return

        self.photo_folder.setText(folder)
        count = len(discover_photos(Path(folder)))
        self.status_label.setText(f"Found {count} JPEG photos in the selected folder.")

    def choose_calibration_photo(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose calibration photo",
            self.photo_folder.text(),
            "JPEG photos (*.jpg *.jpeg *.JPG *.JPEG);;All files (*)",
        )
        if filename:
            self.calibration_photo.setText(filename)

    def show_calibration_photo(self) -> None:
        if not self.calibration_photo.text():
            self._error("Calibration photo missing", "Choose a calibration photo first.")
            return

        pixmap = QPixmap(self.calibration_photo.text())
        if pixmap.isNull():
            self._error("Could not open photo", "Qt could not load the selected calibration photo.")
            return

        PhotoViewerDialog(Path(self.calibration_photo.text()), self).exec()

    def compute_offset(self) -> None:
        if not self.calibration_photo.text():
            self._error("Calibration photo missing", "Choose the photo whose EXIF time should be compared.")
            return
        camera_time = read_taken_at(Path(self.calibration_photo.text()))
        if camera_time is None:
            self._error("No EXIF time", "The calibration photo does not have a readable DateTimeOriginal tag.")
            return

        try:
            actual_time = parse_actual_date_time(
                self.actual_date.date().toString("yyyy-MM-dd"),
                self.actual_clock_time.time().toString("HH:mm:ss"),
                self.actual_timezone.text(),
            )
        except ValueError as exc:
            self._error("Invalid actual time", str(exc))
            return

        camera_time_utc_assumption = camera_time.replace(tzinfo=timezone.utc)
        offset = actual_time - camera_time_utc_assumption
        self.offset_seconds.setValue(int(round(offset.total_seconds())))
        self.status_label.setText(f"Computed clock offset {format_offset(offset.total_seconds())}.")

    def preview_matches(self) -> None:
        if not self.gpx_points:
            self._error("GPX files missing", "Add one or more GPX files with timestamped track points.")
            return
        if not self.photo_folder.text():
            self._error("Photo folder missing", "Choose a folder containing JPEG photos.")
            return

        self.matches = []
        for path in discover_photos(Path(self.photo_folder.text())):
            photo = load_photo(path)
            if photo is None:
                continue
            adjusted = photo.taken_at.replace(tzinfo=timezone.utc) + timedelta(seconds=self.offset_seconds.value())
            point = interpolate(self.gpx_points, adjusted)
            status = "Ready" if point else "Outside GPX time range"
            self.matches.append(Match(photo=photo, adjusted_time_utc=adjusted, point=point, status=status))

        self._populate_table()
        ready = sum(1 for match in self.matches if match.point is not None)
        self.status_label.setText(f"Previewed {len(self.matches)} photos. {ready} can be tagged.")

    def write_tags(self) -> None:
        ready = [match for match in self.matches if match.point is not None]
        if not ready:
            self._error("Nothing to write", "Preview matches first; at least one photo must match the loaded GPX files.")
            return

        reply = QMessageBox.question(
            self,
            "Write GPS tags",
            f"Write GPS tags to {len(ready)} photos?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        failures: list[str] = []
        for match in ready:
            try:
                write_gps_tags(match.photo.path, match.point)
            except Exception as exc:
                failures.append(f"{match.photo.path.name}: {exc}")

        if failures:
            self._error("Some photos could not be tagged", "\n".join(failures[:10]))
        tagged = len(ready) - len(failures)
        self.status_label.setText(f"Wrote GPS tags to {tagged} photos.")

    def _offset_changed(self) -> None:
        self.offset_label.setText(format_offset(self.offset_seconds.value()))

    def _refresh_gpx_list(self) -> None:
        self.matches = []
        self.table.setRowCount(0)

        self.gpx_points = [
            point
            for path in sorted(self.gpx_files)
            for point in self.gpx_files[path]
        ]
        self.gpx_points.sort(key=lambda point: point.time)

        self.gpx_list.clear()
        for path, points in sorted(self.gpx_files.items()):
            item = QListWidgetItem(f"{path.name} ({len(points)} points)")
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            self.gpx_list.addItem(item)

    def _gpx_status_text(self, *, loaded: int = 0, skipped: int = 0, removed: int = 0) -> str:
        parts: list[str] = []
        if loaded:
            parts.append(f"loaded {loaded}")
        if skipped:
            parts.append(f"skipped {skipped} duplicate")
        if removed:
            parts.append(f"removed {removed}")

        action = ", ".join(parts)
        total_files = len(self.gpx_files)
        total_points = len(self.gpx_points)
        if action:
            return f"GPX files {action}. {total_files} loaded with {total_points} total points."
        return f"{total_files} GPX files loaded with {total_points} total points."

    def _default_timezone_text(self) -> str:
        offset = datetime.now().astimezone().utcoffset()
        if offset is None:
            return "Z"
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        total_minutes = abs(total_minutes)
        hours, minutes = divmod(total_minutes, 60)
        return f"{sign}{hours:02d}:{minutes:02d}"

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.matches))
        for row, match in enumerate(self.matches):
            point = match.point
            values = [
                str(match.photo.path),
                match.photo.taken_at.strftime("%Y-%m-%d %H:%M:%S"),
                match.adjusted_time_utc.strftime("%Y-%m-%d %H:%M:%S"),
                f"{point.lat:.7f}" if point else "",
                f"{point.lon:.7f}" if point else "",
                f"{point.ele:.1f} m" if point and point.ele is not None else "",
                match.status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {3, 4, 5, 6}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, column, item)

    def _error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
        self.status_label.setText(message)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
