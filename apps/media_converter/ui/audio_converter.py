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

AUDIO_FORMATS = ["mp3", "wav", "flac", "ogg", "m4a"]


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


class AudioConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Convertidor de Audio")
        self.setGeometry(120, 120, 480, 420)
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

        self.label = QLabel("Selecciona o arrastra un archivo de audio para convertir")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(f"color: {self._colors['text_main']}; font-size: 14pt; font-weight:600;")
        card_layout.addWidget(self.label)

        self.file_label = FileDropLabel(
            self.on_file_dropped,
            [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".mpeg"],
            "audio",
            self,
            placeholder="Arrastra aquí un archivo de audio",
        )
        card_layout.addWidget(self.file_label)

        combo_layout = QHBoxLayout()
        self.from_combo = QComboBox()
        self.from_combo.addItems(AUDIO_FORMATS)
        self.from_combo.setEnabled(False)
        combo_layout.addWidget(QLabel("Formato de origen:"))
        combo_layout.addWidget(self.from_combo)

        self.to_combo = QComboBox()
        self.to_combo.addItems(AUDIO_FORMATS)
        combo_layout.addWidget(QLabel("Formato de destino:"))
        combo_layout.addWidget(self.to_combo)

        card_layout.addLayout(combo_layout)

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

        for i in range(combo_layout.count()):
            widget = combo_layout.itemAt(i).widget()
            if isinstance(widget, QLabel):
                widget.setStyleSheet(f"color: {self._colors['text_muted']};")

        self.layout.addWidget(card)
        self.setLayout(self.layout)
        self.file_path = None
        self.batch_files = []

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
                    self.file_label.setText(f"{len(self.batch_files)} audios seleccionados")

    def select_file(self):
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(self, "Seleccionar Archivos de Audio", "", "Audio (*.mp3 *.wav *.flac *.ogg *.m4a)")
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

    def _refresh_label_and_combos(self):
        if not self.batch_files:
            return
        if len(self.batch_files) == 1:
            self.file_label.setText(os.path.basename(self.batch_files[0]))
            ext = os.path.splitext(self.batch_files[0])[1].lstrip('.').lower()
            if ext == 'mpeg':
                ext = 'mp3'
            if ext in AUDIO_FORMATS:
                idx = self.from_combo.findText(ext)
                if idx != -1:
                    self.from_combo.setCurrentIndex(idx)
                self.from_combo.setEnabled(False)
                dests = [f for f in AUDIO_FORMATS if f != ext]
                self.to_combo.clear()
                self.to_combo.addItems(dests)
        else:
            self.file_label.setText(f"{len(self.batch_files)} audios seleccionados")
            self.from_combo.clear()
            self.from_combo.addItem("varios")
            self.to_combo.clear()
            self.to_combo.addItems(AUDIO_FORMATS)
        self.convert_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Audio")
        if not folder_path:
            return

        valid_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
        self.file_path = None
        for name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, name)
            if os.path.isfile(file_path) and os.path.splitext(name)[1].lower() in valid_exts:
                if file_path not in self.batch_files:
                    self.batch_files.append(file_path)
        if not self.batch_files:
            QMessageBox.warning(self, "Sin archivos", "No se encontraron audios compatibles en la carpeta.")
            return
        self._refresh_label_and_combos()

    def remove_file(self):
        self.file_path = None
        self.batch_files = []
        self.file_label.setText("Arrastra aquí un archivo de audio")
        self.convert_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.from_combo.clear()
        self.from_combo.addItems(AUDIO_FORMATS)
        self.from_combo.setCurrentIndex(0)
        self.from_combo.setEnabled(False)
        self.to_combo.clear()
        self.to_combo.addItems(AUDIO_FORMATS)

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
            progress = AdvancedProgressDialog("Convirtiendo audios...", total, self)
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
                    if from_format == "mpeg":
                        from_format = "mp3"
                    if from_format == to_format:
                        skipped += 1
                    else:
                        base = os.path.splitext(os.path.basename(source))[0]
                        destino_path = os.path.join(output_dir, f"{base}.{to_format}")
                        result = Conversion.AudioFormats.convertir(source, destino_path, formato_destino=to_format)
                        if str(result).startswith("✅"):
                            converted += 1
                        else:
                            failed += 1

                    progress.setLabelText(f"Convirtiendo audios... ({idx}/{total})")
                    progress.setValue(idx)
                    QApplication.processEvents()
            finally:
                progress.close()

            msg = f"Convertidos: {converted}\nFallidos: {failed}"
            if skipped > 0:
                msg += f"\n\nSe omitieron {skipped} audios porque ya estaban en formato {to_format.upper()}."

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
        progress = AdvancedProgressDialog("Convirtiendo audio...", 1, self)
        progress.show()
        QApplication.processEvents()

        try:
            resultado = Conversion.AudioFormats.convertir(self.file_path, destino_path, formato_destino=to_format)
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
    window = AudioConverter()
    window.show()
    sys.exit(app.exec())
