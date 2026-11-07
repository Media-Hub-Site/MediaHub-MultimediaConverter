import sys
import os
import datetime
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QFileDialog, QMessageBox, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
from apps.media_converter.converters import conversion as Conversion
from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    get_button_style,
    get_combo_style,
    get_drop_label_style,
    get_soft_button_style,
    get_remove_button_style,
    get_convert_button_style,
    get_ffmpeg_button_style,
    apply_window_theme,
    make_card_container,
)

VIDEO_FORMATS = ["mp4", "mkv", "avi", "mov", "webm"]
AUDIO_EXTRACT_FORMATS = ["mp3", "wav", "flac", "ogg", "m4a"]


class FileDropLabel(QLabel):
    def __init__(self, on_file_dropped, allowed_extensions, section_name, parent=None, placeholder="Arrastra aquí un archivo"):
        super().__init__(parent)
        self.main_window = parent
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(placeholder)
        self.setStyleSheet(f"{get_drop_label_style()}min-height: 140px;")
        self.setAcceptDrops(True)
        self.file_path = None
        self.on_file_dropped = on_file_dropped
        self.allowed_extensions = tuple(ext.lower() for ext in allowed_extensions)
        self.section_name = section_name

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            valid = any(
                url.toLocalFile().lower().endswith(self.allowed_extensions)
                for url in event.mimeData().urls()
            )
            if valid:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            valid_files = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.toLocalFile().lower().endswith(self.allowed_extensions)
            ]
            invalid_count = len(event.mimeData().urls()) - len(valid_files)
            if valid_files:
                self.on_file_dropped(valid_files)
            if invalid_count > 0:
                QMessageBox.warning(
                    self,
                    "Formato no soportado",
                    f"{invalid_count} archivo(s) no son compatibles con el convertidor de {self.section_name} y fueron ignorados.",
                )
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.main_window, 'open_batch_manager'):
                self.main_window.open_batch_manager()


class VideoConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Convertidor de Video")
        self.setGeometry(120, 120, 520, 480)
        apply_window_theme(self)
        self._colors = get_app_colors()
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(26, 24, 26, 24)
        card, card_layout = make_card_container()

        top_layout = QHBoxLayout()
        back_btn = QPushButton("← Volver")
        back_btn.setFixedWidth(90)
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet(get_soft_button_style())
        top_layout.addWidget(back_btn)
        top_layout.addStretch()
        ffmpeg_btn = QPushButton("Configurar FFmpeg")
        ffmpeg_btn.setFixedWidth(160)
        ffmpeg_btn.clicked.connect(self.show_ffmpeg_help)
        ffmpeg_btn.setStyleSheet(get_ffmpeg_button_style())
        top_layout.addWidget(ffmpeg_btn)
        card_layout.addLayout(top_layout)

        self.label = QLabel("Selecciona o arrastra un archivo de video para convertir")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(f"color: {self._colors['text_main']}; font-size: 14pt; font-weight:600;")
        card_layout.addWidget(self.label)

        self.file_label = FileDropLabel(
            self.on_file_dropped,
            [".mp4", ".mkv", ".avi", ".mov", ".webm"],
            "video",
            self,
            placeholder="Arrastra aquí un archivo de video",
        )
        card_layout.addWidget(self.file_label)

        # ── Formato de origen ──
        from_row = QHBoxLayout()
        from_lbl = QLabel("Formato de origen:")
        self.from_combo = QComboBox()
        self.from_combo.addItems(VIDEO_FORMATS)
        self.from_combo.setEnabled(False)
        self.from_combo.setStyleSheet(get_combo_style())
        from_lbl.setStyleSheet(f"color: {self._colors['text_muted']};")
        from_row.addWidget(from_lbl)
        from_row.addWidget(self.from_combo)
        from_row.addStretch()
        card_layout.addLayout(from_row)

        # ── Toggle: tipo de salida ──
        toggle_row = QHBoxLayout()
        dest_type_lbl = QLabel("Convertir a:")
        dest_type_lbl.setStyleSheet(f"color: {self._colors['text_muted']};")
        toggle_row.addWidget(dest_type_lbl)
        toggle_row.addSpacing(10)

        self.btn_dest_video = QPushButton("\U0001f3ac  Video")
        self.btn_dest_video.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dest_video.setFixedHeight(32)
        self.btn_dest_video.clicked.connect(lambda: self._set_dest_type("video"))

        self.btn_dest_audio = QPushButton("\U0001f3b5  Audio")
        self.btn_dest_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dest_audio.setFixedHeight(32)
        self.btn_dest_audio.clicked.connect(lambda: self._set_dest_type("audio"))

        toggle_row.addWidget(self.btn_dest_video)
        toggle_row.addWidget(self.btn_dest_audio)
        toggle_row.addStretch()
        card_layout.addLayout(toggle_row)

        # ── Formato de destino ──
        to_row = QHBoxLayout()
        self.to_lbl = QLabel("Formato de video:")
        self.to_combo = QComboBox()
        self.to_combo.addItems(VIDEO_FORMATS)
        self.to_combo.setStyleSheet(get_combo_style())
        self.to_lbl.setStyleSheet(f"color: {self._colors['text_muted']};")
        to_row.addWidget(self.to_lbl)
        to_row.addWidget(self.to_combo)
        to_row.addStretch()
        card_layout.addLayout(to_row)

        self.select_button = QPushButton("Seleccionar Archivo")
        self.select_button.clicked.connect(self.select_file)
        self.select_button.setStyleSheet(get_button_style())
        card_layout.addWidget(self.select_button)

        self.select_folder_button = QPushButton("Seleccionar Carpeta")
        self.select_folder_button.clicked.connect(self.select_folder)
        self.select_folder_button.setStyleSheet(get_button_style())
        card_layout.addWidget(self.select_folder_button)

        self.remove_button = QPushButton("Quitar todo")
        self.remove_button.clicked.connect(self.remove_file)
        self.remove_button.setEnabled(False)
        self.remove_button.setStyleSheet(get_remove_button_style())
        card_layout.addWidget(self.remove_button)

        self.convert_button = QPushButton("Convertir Archivo")
        self.convert_button.clicked.connect(self.convert_file)
        self.convert_button.setEnabled(False)
        self.convert_button.setStyleSheet(get_convert_button_style())
        card_layout.addWidget(self.convert_button)

        self.from_combo.setStyleSheet(get_combo_style())
        self.to_combo.setStyleSheet(get_combo_style())

        self.layout.addWidget(card)
        self.setLayout(self.layout)
        self.file_path = None
        self.batch_files = []
        self._dest_type = "video"
        self._update_dest_toggle_styles()

    def open_batch_manager(self):
        if self.batch_files:
            from core.ui.batch_dialog import BatchDialog
            from PyQt6.QtWidgets import QDialog
            dialog = BatchDialog(self.batch_files, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.batch_files = dialog.get_files()
                if len(self.batch_files) == 0:
                    self.remove_file()
                elif len(self.batch_files) == 1:
                    self.file_label.setText(os.path.basename(self.batch_files[0]))
                else:
                    self.file_label.setText(f"{len(self.batch_files)} videos seleccionados")

    def select_file(self):
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(self, "Seleccionar Archivos de Video", "", "Video (*.mp4 *.mkv *.avi *.mov *.webm)")
        if file_paths:
            self.file_path = None
            for fp in file_paths:
                if fp not in self.batch_files:
                    self.batch_files.append(fp)
            self._refresh_label_and_combos()

    def on_file_dropped(self, file_paths):
        self.file_path = None
        for fp in file_paths:
            if fp not in self.batch_files:
                self.batch_files.append(fp)
        self._refresh_label_and_combos()

    def _set_dest_type(self, t: str):
        self._dest_type = t
        self._update_dest_toggle_styles()
        # Repoblar to_combo según tipo
        self.to_combo.clear()
        if t == "video":
            self.to_lbl.setText("Formato de video:")
            src_ext = self.from_combo.currentText()
            formats = [f for f in VIDEO_FORMATS if f != src_ext]
            self.to_combo.addItems(formats if formats else VIDEO_FORMATS)
        else:
            self.to_lbl.setText("Formato de audio:")
            self.to_combo.addItems(AUDIO_EXTRACT_FORMATS)

    def _update_dest_toggle_styles(self):
        _ACTIVE = (
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "from:#6c63ff,to:#a78bfa); color:white; border-radius:6px; "
            "padding:4px 16px; font-weight:bold; border:none; }"
        )
        _INACTIVE = (
            f"QPushButton {{ background-color:#2b2b3b; color:{self._colors['text_muted']}; "
            "border-radius:6px; padding:4px 16px; border:2px solid #3a3a52; }} "
            "QPushButton:hover { background-color:#35354a; color:white; }"
        )
        if self._dest_type == "video":
            self.btn_dest_video.setStyleSheet(_ACTIVE)
            self.btn_dest_audio.setStyleSheet(_INACTIVE)
        else:
            self.btn_dest_video.setStyleSheet(_INACTIVE)
            self.btn_dest_audio.setStyleSheet(_ACTIVE)

    def _refresh_label_and_combos(self):
        if not self.batch_files:
            return
        if len(self.batch_files) == 1:
            self.file_label.setText(os.path.basename(self.batch_files[0]))
            ext = os.path.splitext(self.batch_files[0])[1].lstrip('.').lower()
            if ext in VIDEO_FORMATS:
                idx = self.from_combo.findText(ext)
                if idx != -1:
                    self.from_combo.setCurrentIndex(idx)
                self.from_combo.setEnabled(False)
                # Actualizar to_combo respetando _dest_type
                self._set_dest_type(self._dest_type)
        else:
            self.file_label.setText(f"{len(self.batch_files)} videos seleccionados")
            self.from_combo.clear()
            self.from_combo.addItem("varios")
            self._set_dest_type(self._dest_type)
        self.convert_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Video")
        if not folder_path:
            return
        valid_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
        self.file_path = None
        for name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, name)
            if os.path.isfile(file_path) and os.path.splitext(name)[1].lower() in valid_exts:
                if file_path not in self.batch_files:
                    self.batch_files.append(file_path)
        if not self.batch_files:
            QMessageBox.warning(self, "Sin archivos", "No se encontraron videos compatibles en la carpeta.")
            return
        self._refresh_label_and_combos()

    def remove_file(self):
        self.file_path = None
        self.batch_files = []
        self.file_label.setText("Arrastra aquí un archivo de video")
        self.convert_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.from_combo.clear()
        self.from_combo.addItems(VIDEO_FORMATS)
        self.from_combo.setCurrentIndex(0)
        self.from_combo.setEnabled(False)
        self._dest_type = "video"
        self._update_dest_toggle_styles()
        self.to_lbl.setText("Formato de video:")
        self.to_combo.clear()
        self.to_combo.addItems(VIDEO_FORMATS)

    def choose_output_folder(self):
        return QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de salida")

    def convert_file(self):
        output_dir = self.choose_output_folder()
        if not output_dir:
            return

        if self.batch_files:
            if len(self.batch_files) > 5:
                folder_name = "Conversion_Masiva_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(output_dir, folder_name)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
            to_format = self.to_combo.currentText()
            converted = 0
            skipped = 0
            failed = 0
            total = len(self.batch_files)
            was_cancelled = False
            
            from core.ui.advanced_progress import AdvancedProgressDialog
            progress = AdvancedProgressDialog("Convirtiendo videos...", total, self)
            progress.show()
            QApplication.processEvents()

            try:
                for idx, source in enumerate(self.batch_files, start=1):
                    while progress.is_paused and not progress.is_cancelled:
                        import time
                        time.sleep(0.1)
                        QApplication.processEvents()
                        
                    if progress.is_cancelled:
                        was_cancelled = True
                        break
                        
                    from_format = os.path.splitext(source)[1].lstrip(".").lower()
                    if from_format == to_format:
                        skipped += 1
                    else:
                        base = os.path.splitext(os.path.basename(source))[0]
                        destino_path = os.path.join(output_dir, f"{base}.{to_format}")
                        result = Conversion.VideoFormats.convertir(source, destino_path, formato_destino=to_format)
                        if str(result).startswith("✅"):
                            converted += 1
                        else:
                            failed += 1
                    progress.setLabelText(f"Convirtiendo videos... ({idx}/{total})")
                    progress.setValue(idx)
                    QApplication.processEvents()
            finally:
                progress.close()

            msg = f"Convertidos: {converted}\nFallidos: {failed}"
            if skipped > 0:
                msg += f"\n\nSe omitieron {skipped} videos porque ya estaban en formato {to_format.upper()}."

            if was_cancelled:
                QMessageBox.warning(
                    self,
                    "Conversión Cancelada",
                    f"Proceso cancelado por el usuario.\nSe completaron {converted} archivos de {total} antes de cancelar."
                )
            else:
                QMessageBox.information(
                    self,
                    "Conversión masiva",
                    msg,
                )
            try:
                os.startfile(output_dir)
            except Exception:
                try:
                    subprocess.Popen(["xdg-open", output_dir])
                except Exception:
                    pass
            return

        if not self.file_path:
            QMessageBox.warning(self, "Advertencia", "Por favor selecciona un archivo primero.")
            return
        from_format = self.from_combo.currentText()
        to_format = self.to_combo.currentText()
        if from_format == to_format:
            QMessageBox.warning(self, "Advertencia", "El formato de origen y destino no pueden ser iguales.")
            return
        base = os.path.splitext(os.path.basename(self.file_path))[0]
        destino_path = os.path.join(output_dir, f"{base}.{to_format}")

        from core.ui.advanced_progress import AdvancedProgressDialog
        progress = AdvancedProgressDialog("Convirtiendo video...", 1, self)
        progress.show()
        QApplication.processEvents()

        try:
            resultado = Conversion.VideoFormats.convertir(self.file_path, destino_path, formato_destino=to_format)
        finally:
            progress.close()

        if resultado.startswith('✅'):
            QMessageBox.information(self, "Éxito", resultado)
        else:
            QMessageBox.critical(self, "Error", resultado)

        try:
            os.startfile(output_dir)
        except Exception:
            try:
                subprocess.Popen(['xdg-open', output_dir])
            except Exception:
                pass

    def go_back(self):
        if hasattr(self, "parent_navigator") and self.parent_navigator:
            self.parent_navigator.go_home()
        else:
            from core.ui.hub_window import HubWindow
            try:
                from apps.media_converter.ui.index import LauncherWindow
                self.index_window = LauncherWindow()
            except:
                self.index_window = HubWindow()
            self.index_window.show()
            self.close()

    def show_ffmpeg_help(self):
        QMessageBox.information(
            self,
            "Configurar FFmpeg",
            "FFmpeg es necesario para convertir audio y video.\n\n"
            "Instalación recomendada (PowerShell):\n"
            "winget install \"FFmpeg (Essentials Build)\"\n\n"
            "Si ya lo tienes, también puedes definir:\n"
            "FFMPEG_PATH=C:\\ruta\\a\\ffmpeg.exe",
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoConverter()
    window.show()
    sys.exit(app.exec())
