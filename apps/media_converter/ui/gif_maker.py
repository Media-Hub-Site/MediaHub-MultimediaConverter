import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QMessageBox, QFrame, QComboBox,
    QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    make_card_container,
    get_combo_style,
)
from apps.media_converter.converters.conversion import _find_ffmpeg


class GifConvertThread(QThread):
    progress = pyqtSignal(int, str)
    finished_success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, input_path, output_path, start_sec, duration_sec, fps, width):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.start_sec = start_sec
        self.duration_sec = duration_sec
        self.fps = fps
        self.width = width

    def run(self):
        try:
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                self.error.emit("No se encontró FFmpeg en el sistema.")
                return

            self.progress.emit(25, "Analizando colores y generando paleta óptima...")

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Filtro de 2 pasadas en una sola tubería con lavfi (paleta de alta fidelidad)
            filter_complex = (
                f"fps={self.fps},scale={self.width}:-1:flags=lanczos,split[s0][s1];"
                f"[s0]palettegen=stats_mode=diff[p];"
                f"[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
            )

            cmd = [
                ffmpeg_path, "-y",
                "-ss", str(self.start_sec),
                "-t", str(self.duration_sec),
                "-i", self.input_path,
                "-vf", filter_complex,
                self.output_path
            ]

            self.progress.emit(55, "Renderizando GIF en alta definición...")
            proc = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True, text=True)

            if proc.returncode != 0:
                self.error.emit(f"Error generando el GIF:\n{proc.stderr[-400:]}")
                return

            self.progress.emit(100, "¡GIF creado con éxito!")
            self.finished_success.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


class GifMakerUI(QWidget):
    """Interfaz gráfica para convertir videos en GIFs de alta calidad."""

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

        # Header
        header = QLabel("Creador de GIF")
        header.setStyleSheet(f"font-size: 19pt; font-weight: 800; color: {self._colors['text_main']};")
        desc = QLabel("Convierte fragmentos de video en GIFs fluidos de alta definición sin colores pixelados.")
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

        self.drop_label = QLabel("Arrastra el video para convertir a GIF")
        self.drop_label.setStyleSheet(f"color: {self._colors['text_main']}; font-size: 11pt; font-weight: 600;")
        self.file_info_label = QLabel("Soporta MP4, MKV, MOV, AVI, WebM")
        self.file_info_label.setStyleSheet(f"color: {self._colors['text_muted']}; font-size: 9pt;")

        drop_layout.addWidget(self.drop_label, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.file_info_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.drop_zone.mousePressEvent = lambda e: self.select_file()
        self.drop_zone.dragEnterEvent = self.drag_enter_event
        self.drop_zone.dropEvent = self.drop_event

        card_layout.addWidget(self.drop_zone)
        card_layout.addSpacing(8)

        # Opciones de GIF
        opts_box = QFrame()
        opts_box.setStyleSheet(f"background-color: {self._colors['bg']}; border-radius: 12px; padding: 12px;")
        opts_layout = QVBoxLayout(opts_box)
        opts_layout.setSpacing(12)

        lbl_opts = QLabel("Ajustes del GIF:")
        lbl_opts.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 700; font-size: 10.5pt;")
        opts_layout.addWidget(lbl_opts)

        row_time = QHBoxLayout()
        lbl_start = QLabel("Segundo inicial:")
        lbl_start.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 600;")
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(0.0, 9999.0)
        self.spin_start.setValue(0.0)
        self.spin_start.setSuffix(" s")
        self._style_spin(self.spin_start)

        lbl_dur = QLabel("Duración:")
        lbl_dur.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 600;")
        self.spin_dur = QDoubleSpinBox()
        self.spin_dur.setRange(0.5, 60.0)
        self.spin_dur.setValue(4.0)
        self.spin_dur.setSuffix(" s")
        self._style_spin(self.spin_dur)

        row_time.addWidget(lbl_start)
        row_time.addWidget(self.spin_start)
        row_time.addSpacing(20)
        row_time.addWidget(lbl_dur)
        row_time.addWidget(self.spin_dur)
        row_time.addStretch()
        opts_layout.addLayout(row_time)

        row_quality = QHBoxLayout()
        lbl_res = QLabel("Resolución (Ancho):")
        lbl_res.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 600;")
        self.combo_res = QComboBox()
        self.combo_res.setStyleSheet(get_combo_style())
        self.combo_res.addItems(["360 px (Ligero)", "480 px (Estándar)", "720 px (HD)", "Personalizado"])
        self.combo_res.setCurrentIndex(1)

        lbl_fps = QLabel("Fluidez (FPS):")
        lbl_fps.setStyleSheet(f"color: {self._colors['text_main']}; font-weight: 600;")
        self.combo_fps = QComboBox()
        self.combo_fps.setStyleSheet(get_combo_style())
        self.combo_fps.addItems(["15 FPS (Económico)", "24 FPS (Animación fluida)", "30 FPS (Ultra suave)"])
        self.combo_fps.setCurrentIndex(1)

        row_quality.addWidget(lbl_res)
        row_quality.addWidget(self.combo_res)
        row_quality.addSpacing(20)
        row_quality.addWidget(lbl_fps)
        row_quality.addWidget(self.combo_fps)
        row_quality.addStretch()
        opts_layout.addLayout(row_quality)

        card_layout.addWidget(opts_box)
        card_layout.addSpacing(10)

        # Barra de progreso y botón de acción
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

        self.btn_create_gif = QPushButton("Crear GIF")
        self.btn_create_gif.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_gif.setFixedHeight(46)
        self.btn_create_gif.setFixedWidth(220)
        self.btn_create_gif.setEnabled(False)
        self.btn_create_gif.setStyleSheet(f"""
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
        self.btn_create_gif.clicked.connect(self.start_gif)
        bottom_layout.addWidget(self.btn_create_gif)
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
                min-width: 80px;
            }}
        """)

    def drag_enter_event(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(urls[0].toLocalFile().lower().endswith(ext) for ext in [".mp4", ".mkv", ".mov", ".avi", ".webm"]):
                event.acceptProposedAction()

    def drop_event(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_file(path)

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Video", "", "Videos (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if file:
            self._set_file(file)

    def _set_file(self, file_path):
        self.file_path = file_path
        name = os.path.basename(file_path)
        self.drop_label.setText(name)
        self.file_info_label.setText("Video seleccionado para extracción de GIF")
        self.btn_create_gif.setEnabled(True)
        self.status_label.setText("")

    def start_gif(self):
        if not self.file_path or not os.path.exists(self.file_path):
            return

        base, _ = os.path.splitext(self.file_path)
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar GIF", f"{base}.gif", "Animación GIF (*.gif)"
        )
        if not output_path:
            return

        start_sec = self.spin_start.value()
        dur_sec = self.spin_dur.value()

        res_map = {0: 360, 1: 480, 2: 720, 3: 480}
        width = res_map.get(self.combo_res.currentIndex(), 480)

        fps_map = {0: 15, 1: 24, 2: 30}
        fps = fps_map.get(self.combo_fps.currentIndex(), 24)

        self.btn_create_gif.setEnabled(False)
        self.drop_zone.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)

        self.worker = GifConvertThread(
            self.file_path, output_path, start_sec, dur_sec, fps, width
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_success)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_label.setText(msg)

    def _on_success(self, output_path):
        self.btn_create_gif.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.progress_bar.setVisible(False)
        size_kb = os.path.getsize(output_path) / 1024
        self.status_label.setText(f"GIF generado: {size_kb:.1f} KB")
        QMessageBox.information(
            self, "GIF Creado",
            f"Tu GIF de alta definición se ha creado correctamente.\n\n"
            f"Tamaño: {size_kb:.1f} KB\nRuta: {output_path}"
        )

    def _on_error(self, err):
        self.btn_create_gif.setEnabled(True)
        self.drop_zone.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error al crear GIF")
        QMessageBox.critical(self, "Error", f"Ocurrió un error al generar el GIF:\n{err}")
