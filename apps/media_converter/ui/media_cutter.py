import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QMessageBox, QFrame, QDoubleSpinBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    make_card_container,
)
from apps.media_converter.converters.conversion import _find_ffmpeg


class MediaCutThread(QThread):
    progress = pyqtSignal(int, str)
    finished_success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, input_path, output_path, start_sec, end_sec, stream_copy):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.stream_copy = stream_copy

    def run(self):
        try:
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                self.error.emit("No se encontró FFmpeg.")
                return

            self.progress.emit(20, "Preparando corte...")
            duration = max(self.end_sec - self.start_sec, 0.1)

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Si stream_copy es True, el corte es instantáneo sin pérdida (-c copy)
            if self.stream_copy:
                cmd = [
                    ffmpeg_path, "-y",
                    "-ss", str(self.start_sec),
                    "-t", str(duration),
                    "-i", self.input_path,
                    "-c", "copy",
                    self.output_path
                ]
            else:
                cmd = [
                    ffmpeg_path, "-y",
                    "-ss", str(self.start_sec),
                    "-t", str(duration),
                    "-i", self.input_path,
                    self.output_path
                ]

            self.progress.emit(60, "Recortando archivo multimedia...")
            proc = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True, text=True)

            if proc.returncode != 0:
                # Fallback sin -c copy si falló por keyframes
                cmd_fallback = [
                    ffmpeg_path, "-y",
                    "-ss", str(self.start_sec),
                    "-t", str(duration),
                    "-i", self.input_path,
                    self.output_path
                ]
                proc2 = subprocess.run(cmd_fallback, startupinfo=startupinfo, capture_output=True, text=True)
                if proc2.returncode != 0:
                    self.error.emit(f"Error al cortar:\n{proc2.stderr[-300:]}")
                    return

            self.progress.emit(100, "¡Corte completado!")
            self.finished_success.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


class MediaCutterUI(QWidget):
    """Interfaz gráfica unificada para recortar video y audio con velocidad instantánea."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = get_app_colors()
        self.file_path = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 24)
        main_layout.setSpacing(16)

        card, card_layout = make_card_container()

        header = QLabel("✂️ Cortador Multimedia")
        header.setStyleSheet(f"font-size: 19pt; font-weight: 800; color: {self._colors['text_main']};")
        desc = QLabel("Recorta fragmentos de cualquier video o audio sin perder calidad y en cuestión de segundos.")
        desc.setStyleSheet(f"color: {self._colors['text_muted']}; font-size: 10.5pt;")
        card_layout.addWidget(header)
        card_layout.addWidget(desc)
        card_layout.addSpacing(10)

        # Drop Zone
        self.drop_zone = QFrame()
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.setFixedHeight(140)
        self.drop_zone.setStyleSheet(f"""
            QFrame {{
                background-color: {self._colors['bg']};
                border: 2px dashed {self._colors['border']};
                border-radius: 14px;
            }}
            QFrame:hover {{
                border-color: {self._colors['accent']};
                background-color: {self._colors['accent_soft']};
            }}
        """)
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.drop_label = QLabel("📁 Arrastra un video o audio aquí para recortar")
        self.drop_label.setStyleSheet(f"color: {self._colors['text_main']}; font-size: 11pt; font-weight: 600;")
        self.file_info_label = QLabel("Soporta MP4, MKV, MOV, MP3, WAV, AAC, FLAC, OGG y más")
        self.file_info_label.setStyleSheet(f"color: {self._colors['text_muted']}; font-size: 9pt;")

        drop_layout.addWidget(self.drop_label, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.file_info_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.drop_zone.mousePressEvent = lambda e: self.select_file()
        self.drop_zone.dragEnterEvent = self.drag_enter_event
        self.drop_zone.dropEvent = self.drop_event

        card_layout.addWidget(self.drop_zone)
        card_layout.addSpacing(8)

        # Opciones de Corte
        opts_box = QFrame()
        opts_box.setStyleSheet(f"background-color: {self._colors['bg']}; border-radius: 12px; padding: 12px;")
        opts_layout = QVBoxLayout(opts_box)
        opts_layout.setSpacing(12)

        lbl_opts = QLabel("⏱️ Puntos de Corte:")
        lbl_opts.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 700; font-size: 10.5pt;")
        opts_layout.addWidget(lbl_opts)

        row_time = QHBoxLayout()
        lbl_start = QLabel("Punto de inicio:")
        lbl_start.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 600;")
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(0.0, 999999.0)
        self.spin_start.setValue(0.0)
        self.spin_start.setSuffix(" s")
        self._style_spin(self.spin_start)

        lbl_end = QLabel("Punto final:")
        lbl_end.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 600;")
        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(0.1, 999999.0)
        self.spin_end.setValue(30.0)
        self.spin_end.setSuffix(" s")
        self._style_spin(self.spin_end)

        row_time.addWidget(lbl_start)
        row_time.addWidget(self.spin_start)
        row_time.addSpacing(25)
        row_time.addWidget(lbl_end)
        row_time.addWidget(self.spin_end)
        row_time.addStretch()
        opts_layout.addLayout(row_time)

        self.chk_lossless = QCheckBox("⚡ Modo Ultra Rápido sin pérdida (Stream Copy directo)")
        self.chk_lossless.setChecked(True)
        self.chk_lossless.setStyleSheet(f"color: {self._colors['text_muted']}; font-weight: 600; font-size: 9.5pt;")
        opts_layout.addWidget(self.chk_lossless)

        card_layout.addWidget(opts_box)
        card_layout.addSpacing(10)

        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {self._colors['bg']};
                border-radius: 6px;
                border: 1px solid {self._colors['border']};
            }}
            QProgressBar::chunk {{
                background: {self._colors['accent']};
                border-radius: 5px;
            }}
        """)
        card_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {self._colors['text_muted']}; font-weight: 600;")
        card_layout.addWidget(self.status_label)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_cut = QPushButton("✂️ Recortar Archivo")
        self.btn_cut.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cut.setFixedHeight(46)
        self.btn_cut.setFixedWidth(220)
        self.btn_cut.setEnabled(False)
        self.btn_cut.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                font-size: 11pt;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {self._colors['border']};
                color: {self._colors['text_muted']};
            }}
        """)
        self.btn_cut.clicked.connect(self.start_cut)
        bottom_layout.addWidget(self.btn_cut)
        bottom_layout.addStretch()

        card_layout.addLayout(bottom_layout)
        main_layout.addWidget(card)

    def _style_spin(self, spin):
        spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {self._colors['card']};
                color: {self._colors['text_main']};
                border: 1px solid {self._colors['border']};
                border-radius: 8px;
                padding: 4px 8px;
                font-weight: 600;
                min-width: 90px;
            }}
        """)

    def drag_enter_event(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_file(path)

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo Multimedia", "", "Multimedia (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.flac *.aac *.ogg *.m4a)"
        )
        if file:
            self._set_file(file)

    def _set_file(self, file_path):
        self.file_path = file_path
        name = os.path.basename(file_path)
        self.drop_label.setText(f"📁 {name}")
        self.file_info_label.setText("Archivo listo para recortar")
        self.btn_cut.setEnabled(True)
        self.status_label.setText("")

    def start_cut(self):
        if not self.file_path or not os.path.exists(self.file_path):
            return

        start_val = self.spin_start.value()
        end_val = self.spin_end.value()
        if start_val >= end_val:
            QMessageBox.warning(self, "Rango Inválido", "El punto de inicio debe ser menor que el punto final.")
            return

        base, ext = os.path.splitext(self.file_path)
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Archivo Recortado", f"{base}_recorte{ext}", f"Archivo ({ext})"
        )
        if not output_path:
            return

        self.btn_cut.setEnabled(False)
        self.drop_zone.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(15)

        stream_copy = self.chk_lossless.isChecked()
        self.worker = MediaCutThread(
            self.file_path, output_path, start_val, end_val, stream_copy
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_success)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_label.setText(msg)

    def _on_success(self, output_path):
        self.btn_cut.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("✅ Archivo recortado guardado con éxito")
        QMessageBox.information(
            self, "Recorte Completado",
            f"El fragmento se ha recortado correctamente:\n\n{output_path}"
        )

    def _on_error(self, err):
        self.btn_cut.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("❌ Error al recortar")
        QMessageBox.critical(self, "Error", f"Ocurrió un error al recortar el archivo:\n{err}")
