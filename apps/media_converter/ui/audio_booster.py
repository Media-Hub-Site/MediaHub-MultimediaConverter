import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QMessageBox, QFrame, QSlider,
    QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    make_card_container,
)
from apps.media_converter.converters.conversion import _find_ffmpeg


class AudioBoostThread(QThread):
    progress = pyqtSignal(int, str)
    finished_success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, input_path, output_path, volume_multiplier, normalize):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.volume_multiplier = volume_multiplier
        self.normalize = normalize

    def run(self):
        try:
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                self.error.emit("No se encontró FFmpeg en el sistema.")
                return

            self.progress.emit(25, "Analizando niveles de audio...")

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Filtros de audio
            filters = []
            if self.normalize:
                # EBU R128 loudnorm para nivelado profesional
                filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
            if self.volume_multiplier != 1.0:
                filters.append(f"volume={self.volume_multiplier:.2f}")

            filter_str = ",".join(filters) if filters else "volume=1.0"

            # Detectar si el contenedor de entrada es video o solo audio
            _, ext = os.path.splitext(self.input_path)
            is_video = ext.lower() in [".mp4", ".mkv", ".mov", ".avi", ".webm"]

            if is_video:
                # Si es video, mantenemos el stream de video intacto (-c:v copy) y filtramos solo el audio
                cmd = [
                    ffmpeg_path, "-y",
                    "-i", self.input_path,
                    "-c:v", "copy",
                    "-af", filter_str,
                    self.output_path
                ]
            else:
                cmd = [
                    ffmpeg_path, "-y",
                    "-i", self.input_path,
                    "-af", filter_str,
                    self.output_path
                ]

            self.progress.emit(60, "Procesando y amplificando audio...")
            proc = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True, text=True)

            if proc.returncode != 0:
                self.error.emit(f"Error procesando audio:\n{proc.stderr[-300:]}")
                return

            self.progress.emit(100, "¡Audio amplificado y guardado!")
            self.finished_success.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


class AudioBoosterUI(QWidget):
    """Interfaz gráfica para amplificar y normalizar volumen de audio o video."""

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

        header = QLabel("🔊 Amplificador de Volumen")
        header.setStyleSheet(f"font-size: 19pt; font-weight: 800; color: {self._colors['text_main']};")
        desc = QLabel("Sube el volumen de grabaciones bajas y normaliza niveles desiguales en audios y videos.")
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

        self.drop_label = QLabel("📁 Arrastra un archivo de audio o video aquí")
        self.drop_label.setStyleSheet(f"color: {self._colors['text_main']}; font-size: 11pt; font-weight: 600;")
        self.file_info_label = QLabel("Soporta MP3, WAV, M4A, FLAC, MP4, MKV y más")
        self.file_info_label.setStyleSheet(f"color: {self._colors['text_muted']}; font-size: 9pt;")

        drop_layout.addWidget(self.drop_label, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.file_info_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.drop_zone.mousePressEvent = lambda e: self.select_file()
        self.drop_zone.dragEnterEvent = self.drag_enter_event
        self.drop_zone.dropEvent = self.drop_event

        card_layout.addWidget(self.drop_zone)
        card_layout.addSpacing(8)

        # Panel de Ajustes
        opts_box = QFrame()
        opts_box.setStyleSheet(f"background-color: {self._colors['bg']}; border-radius: 12px; padding: 14px;")
        opts_layout = QVBoxLayout(opts_box)
        opts_layout.setSpacing(12)

        lbl_gain = QLabel("🎚️ Multiplicador de Volumen:")
        lbl_gain.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 700; font-size: 10.5pt;")
        opts_layout.addWidget(lbl_gain)

        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(50, 400)  # 50% a 400% (0.5x a 4.0x)
        self.slider.setValue(150)      # 150% (+50%)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {self._colors['card']};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self._colors['accent']};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                border: 2px solid {self._colors['accent']};
                width: 18px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 9px;
            }}
        """)

        self.lbl_slider_val = QLabel("150% (+50%)")
        self.lbl_slider_val.setFixedWidth(100)
        self.lbl_slider_val.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 700; font-size: 11pt;")

        self.slider.valueChanged.connect(self._on_slider_changed)

        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.lbl_slider_val)
        opts_layout.addLayout(slider_row)

        self.chk_norm = QCheckBox("✨ Normalización inteligente EBU R128 (Equilibra voces bajas y picos altos)")
        self.chk_norm.setChecked(True)
        self.chk_norm.setStyleSheet(f"color: {self._colors['text_muted']}; font-weight: 600; font-size: 9.5pt;")
        opts_layout.addWidget(self.chk_norm)

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

        self.btn_boost = QPushButton("🔊 Aplicar y Guardar")
        self.btn_boost.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_boost.setFixedHeight(46)
        self.btn_boost.setFixedWidth(220)
        self.btn_boost.setEnabled(False)
        self.btn_boost.setStyleSheet(f"""
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
        self.btn_boost.clicked.connect(self.start_boost)
        bottom_layout.addWidget(self.btn_boost)
        bottom_layout.addStretch()

        card_layout.addLayout(bottom_layout)
        main_layout.addWidget(card)

    def _on_slider_changed(self, val):
        mult = val / 100.0
        diff = val - 100
        sign = "+" if diff > 0 else ""
        self.lbl_slider_val.setText(f"{val}% ({sign}{diff}%)")

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
            self, "Seleccionar Audio o Video", "",
            "Multimedia (*.mp3 *.wav *.m4a *.flac *.aac *.ogg *.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if file:
            self._set_file(file)

    def _set_file(self, file_path):
        self.file_path = file_path
        name = os.path.basename(file_path)
        self.drop_label.setText(f"📁 {name}")
        self.file_info_label.setText("Listo para amplificar y normalizar volumen")
        self.btn_boost.setEnabled(True)
        self.status_label.setText("")

    def start_boost(self):
        if not self.file_path or not os.path.exists(self.file_path):
            return

        base, ext = os.path.splitext(self.file_path)
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Archivo con Volumen Amplificado", f"{base}_amplificado{ext}", f"Archivo ({ext})"
        )
        if not output_path:
            return

        self.btn_boost.setEnabled(False)
        self.drop_zone.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(15)

        mult = self.slider.value() / 100.0
        norm = self.chk_norm.isChecked()

        self.worker = AudioBoostThread(self.file_path, output_path, mult, norm)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_success)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_label.setText(msg)

    def _on_success(self, output_path):
        self.btn_boost.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("✅ Archivo amplificado guardado con éxito")
        QMessageBox.information(
            self, "Volumen Amplificado",
            f"El archivo se procesó correctamente:\n\n{output_path}"
        )

    def _on_error(self, err):
        self.btn_boost.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("❌ Error al procesar")
        QMessageBox.critical(self, "Error", f"Ocurrió un error al amplificar el audio:\n{err}")
