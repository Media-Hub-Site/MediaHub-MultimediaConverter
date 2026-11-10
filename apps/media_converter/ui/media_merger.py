import os
import sys
import subprocess
import tempfile
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QMessageBox, QFrame, QListWidget,
    QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    make_card_container,
)
from apps.media_converter.converters.conversion import _find_ffmpeg


class MediaMergeThread(QThread):
    progress = pyqtSignal(int, str)
    finished_success = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, file_list, output_path, is_video):
        super().__init__()
        self.file_list = file_list
        self.output_path = output_path
        self.is_video = is_video

    def run(self):
        try:
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                self.error.emit("No se encontró FFmpeg en el sistema.")
                return

            self.progress.emit(20, "Preparando lista de archivos...")

            # Crear archivo de texto temporal para el demuxer concat de FFmpeg
            temp_concat = os.path.join(tempfile.gettempdir(), "concat_list.txt")
            with open(temp_concat, "w", encoding="utf-8") as f:
                for path in self.file_list:
                    # FFmpeg concat format requiere escapar comillas simples
                    clean_path = path.replace("'", "'\\''")
                    f.write(f"file '{clean_path}'\n")

            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.progress.emit(50, "Fusionando archivos en una sola pista...")

            # Intentar primero concat directo sin pérdida (-c copy)
            cmd_fast = [
                ffmpeg_path, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", temp_concat,
                "-c", "copy",
                self.output_path
            ]
            proc = subprocess.run(cmd_fast, startupinfo=startupinfo, capture_output=True, text=True)

            if proc.returncode != 0:
                # Si los codecs o resoluciones difieren, recodificar de forma compatible
                self.progress.emit(65, "Recodificando para compatibilidad uniforme...")
                if self.is_video:
                    cmd_reencode = [
                        ffmpeg_path, "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", temp_concat,
                        "-c:v", "libx264", "-preset", "faster",
                        "-c:a", "aac",
                        self.output_path
                    ]
                else:
                    cmd_reencode = [
                        ffmpeg_path, "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", temp_concat,
                        "-c:a", "libmp3lame", "-b:a", "192k",
                        self.output_path
                    ]
                proc2 = subprocess.run(cmd_reencode, startupinfo=startupinfo, capture_output=True, text=True)
                if proc2.returncode != 0:
                    self.error.emit(f"Error al fusionar archivos:\n{proc2.stderr[-300:]}")
                    return

            if os.path.exists(temp_concat):
                try:
                    os.remove(temp_concat)
                except Exception:
                    pass

            self.progress.emit(100, "¡Archivos fusionados con éxito!")
            self.finished_success.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


class MediaMergerUI(QWidget):
    """Interfaz gráfica para unir y fusionar múltiples pistas de audio o clips de video."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = get_app_colors()
        self.files = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 24)
        main_layout.setSpacing(16)

        card, card_layout = make_card_container()

        header = QLabel("Unificador Multimedia")
        header.setStyleSheet(f"font-size: 19pt; font-weight: 800; color: {self._colors['text_main']};")
        desc = QLabel("Une varios clips de video o canciones en un único archivo continuo y ordenado.")
        desc.setStyleSheet(f"color: {self._colors['text_muted']}; font-size: 10.5pt;")
        card_layout.addWidget(header)
        card_layout.addWidget(desc)
        card_layout.addSpacing(10)

        # Drop Zone y Botones de Lista
        top_list_row = QHBoxLayout()
        self.lbl_count = QLabel("0 archivos añadidos")
        self.lbl_count.setStyleSheet(f"color: {self._colors['text_muted']}; font-weight: 600; font-size: 10pt;")
        top_list_row.addWidget(self.lbl_count)
        top_list_row.addStretch()

        btn_add = QPushButton("Añadir Archivos")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['card']};
                color: {self._colors['text_main']};
                border: 1px solid {self._colors['border']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_soft']};
                border-color: {self._colors['accent']};
            }}
        """)
        btn_add.clicked.connect(self.select_files)
        top_list_row.addWidget(btn_add)

        btn_clear = QPushButton("Limpiar")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['card']};
                color: #FF5A5A;
                border: 1px solid {self._colors['border']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(235, 87, 87, 0.15);
            }}
        """)
        btn_clear.clicked.connect(self.clear_files)
        top_list_row.addWidget(btn_clear)

        card_layout.addLayout(top_list_row)

        # Lista de Archivos para Concat
        self.list_widget = QListWidget()
        self.list_widget.setFixedHeight(180)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {self._colors['bg']};
                border: 1px solid {self._colors['border']};
                border-radius: 12px;
                padding: 8px;
                color: {self._colors['text_main']};
                font-size: 10pt;
            }}
            QListWidget::item {{
                padding: 6px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: {self._colors['accent']};
                color: #FFFFFF;
            }}
        """)
        self.list_widget.dragEnterEvent = self.drag_enter_event
        self.list_widget.dropEvent = self.drop_event
        card_layout.addWidget(self.list_widget)

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

        self.btn_merge = QPushButton("Fusionar Archivos")
        self.btn_merge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_merge.setFixedHeight(46)
        self.btn_merge.setFixedWidth(220)
        self.btn_merge.setEnabled(False)
        self.btn_merge.setStyleSheet(f"""
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
        self.btn_merge.clicked.connect(self.start_merge)
        bottom_layout.addWidget(self.btn_merge)
        bottom_layout.addStretch()

        card_layout.addLayout(bottom_layout)
        main_layout.addWidget(card)

    def drag_enter_event(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for u in urls:
            path = u.toLocalFile()
            if os.path.isfile(path) and path not in self.files:
                self.files.append(path)
        self._refresh_list()

    def select_files(self):
        selected, _ = QFileDialog.getOpenFileNames(
            self, "Añadir Archivos para Unir", "",
            "Multimedia (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.flac *.m4a *.aac)"
        )
        for s in selected:
            if s not in self.files:
                self.files.append(s)
        self._refresh_list()

    def clear_files(self):
        self.files.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        for i, f in enumerate(self.files):
            name = os.path.basename(f)
            item = QListWidgetItem(f"{i + 1}.  {name}")
            self.list_widget.addItem(item)
        count = len(self.files)
        self.lbl_count.setText(f"{count} archivos añadidos")
        self.btn_merge.setEnabled(count >= 2)
        self.status_label.setText("")

    def start_merge(self):
        if len(self.files) < 2:
            return

        first_ext = os.path.splitext(self.files[0])[1].lower()
        is_video = first_ext in [".mp4", ".mkv", ".mov", ".avi", ".webm"]

        default_out = "video_unido.mp4" if is_video else "audio_unido.mp3"
        filter_str = "Video (*.mp4)" if is_video else "Audio (*.mp3)"

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Archivo Fusionado", default_out, filter_str
        )
        if not output_path:
            return

        self.btn_merge.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(15)

        self.worker = MediaMergeThread(self.files, output_path, is_video)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_success)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_label.setText(msg)

    def _on_success(self, output_path):
        self.btn_merge.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Archivos unidos correctamente")
        QMessageBox.information(
            self, "Fusión Exitosa",
            f"Se unieron los {len(self.files)} archivos correctamente en:\n\n{output_path}"
        )

    def _on_error(self, err):
        self.btn_merge.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error al unir archivos")
        QMessageBox.critical(self, "Error", f"Ocurrió un error al fusionar los archivos:\n{err}")
