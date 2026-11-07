import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from apps.media_converter.ui.audio_converter import AudioConverter
from apps.media_converter.ui.video_converter import VideoConverter
from apps.media_converter.ui.images_converter import ImageConverter
from apps.media_converter.ui.image_rescaler import ImageRescaler
from apps.media_converter.ui.audio_cut import AudioCutUI
from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    get_soft_button_style,
    apply_window_theme,
    make_card_container,
)


class LauncherWindow(QWidget):
    """Pantalla de inicio que permite elegir el tipo de conversión."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elige tu tipo de conversión")
        self.setGeometry(200, 200, 360, 220)
        apply_window_theme(self)
        self._colors = get_app_colors()
        self.init_ui()

    def init_ui(self):
        self.setGeometry(160, 120, 900, 720)

        # Configurar Stacked Widget
        self.stacked_widget = QStackedWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.stacked_widget)
        self.setLayout(main_layout)

        # Construir la página del menú
        self.menu_page = QWidget()
        root_layout = QVBoxLayout(self.menu_page)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(0)
        main_card, layout = make_card_container()

        title = QLabel("Elige tu tipo de conversión")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 22pt; font-weight: 700; color: {self._colors['text_main']}; margin-bottom: 8px;")
        layout.addWidget(title)

        icons_layout = QHBoxLayout()
        icons_layout.setSpacing(40)

        def make_block(icon_filename, label_text, handler):
            v = QVBoxLayout()
            btn = QPushButton()
            import sys
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, 'assets', 'apps', 'media_converter', icon_filename)
            else:
                icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'assets', 'apps', 'media_converter', icon_filename))
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(180, 180))
            btn.setFixedSize(200, 200)
            btn.setStyleSheet(
                f"QPushButton{{background:{self._colors['card']};border-radius:20px;border:1px solid {self._colors['border']};}}"
                f"QPushButton:hover{{background:{self._colors['accent_soft']}}}"
            )
            btn.clicked.connect(handler)
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {self._colors['text_muted']}; font-weight:600; margin-top:8px;")
            v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
            v.addWidget(lbl)
            return v

        icons_layout.addLayout(make_block('ImagenIcon.png', 'Imagen', self.open_image_converter))
        icons_layout.addLayout(make_block('AudioIcon.png', 'Audio', self.open_audio_converter))
        icons_layout.addLayout(make_block('VideoIcon.png', 'Video', self.open_video_converter))
        icons_layout.addLayout(make_block('Upscaler.png', 'Reescalar', self.open_image_rescaler))
        icons_layout.addLayout(make_block('audiocut.webp', 'Cortar Audio', self.open_audio_cut))

        layout.addLayout(icons_layout)

        footer = QHBoxLayout()
        footer.addStretch()
        
        real_exit_btn = QPushButton("Salir")
        real_exit_btn.setFixedWidth(120)
        real_exit_btn.clicked.connect(self.close)
        real_exit_btn.setStyleSheet(get_soft_button_style())
        footer.addWidget(real_exit_btn)
        
        exit_btn = QPushButton("← Volver al Hub")
        exit_btn.setFixedWidth(160)
        exit_btn.clicked.connect(self.go_to_hub)
        exit_btn.setStyleSheet(get_soft_button_style())
        footer.addWidget(exit_btn)
        
        footer.addStretch()

        layout.addStretch()
        layout.addLayout(footer)

        root_layout.addWidget(main_card)
        
        self.stacked_widget.addWidget(self.menu_page)
        self.loaded_pages = {}

    def go_home(self):
        self.stacked_widget.setCurrentWidget(self.menu_page)

    def show_tool(self, tool_id, ToolClass):
        if tool_id not in self.loaded_pages:
            tool_widget = ToolClass()
            tool_widget.parent_navigator = self
            self.stacked_widget.addWidget(tool_widget)
            self.loaded_pages[tool_id] = tool_widget
        self.stacked_widget.setCurrentWidget(self.loaded_pages[tool_id])

    def open_audio_cut(self):
        try:
            self.show_tool('audio_cut', AudioCutUI)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el cortador de audio:\n{e}")

    def open_image_rescaler(self):
        try:
            self.show_tool('image_rescaler', ImageRescaler)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el reescalador:\n{e}")

    def open_image_converter(self):
        try:
            self.show_tool('image_converter', ImageConverter)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el conversor de imágenes:\n{e}")

    def open_audio_converter(self):
        try:
            self.show_tool('audio_converter', AudioConverter)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el conversor de audio:\n{e}")

    def open_video_converter(self):
        try:
            self.show_tool('video_converter', VideoConverter)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir el conversor de video:\n{e}")

    def go_to_hub(self):
        from core.ui.hub_window import HubWindow
        self.hub_window = HubWindow()
        self.hub_window.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
