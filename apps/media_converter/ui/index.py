import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QStackedWidget, QFrame, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from apps.media_converter.ui.audio_converter import AudioConverter
from apps.media_converter.ui.video_converter import VideoConverter
from apps.media_converter.ui.images_converter import ImageConverter
from apps.media_converter.ui.image_rescaler import ImageRescaler
from apps.media_converter.ui.video_compressor import VideoCompressorUI
from apps.media_converter.ui.gif_maker import GifMakerUI
from apps.media_converter.ui.media_cutter import MediaCutterUI
from apps.media_converter.ui.audio_booster import AudioBoosterUI
from apps.media_converter.ui.media_merger import MediaMergerUI
from apps.media_converter.ui.ui_theme import (
    get_app_colors,
    apply_window_theme,
)
from apps.media_converter.i18n import t, get_current_language


class LauncherWindow(QWidget):
    """Ventana principal de Multimedia Converter con barra lateral moderna y suite completa de herramientas."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.resize(1120, 780)
        self.setMinimumSize(1000, 700)
        apply_window_theme(self)
        self._colors = get_app_colors()

        icon_path = self._get_asset_path(os.path.join("hub", "Media-Hub.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.loaded_pages = {}
        self.nav_buttons = {}
        self.init_ui()

    def _get_asset_path(self, subpath: str) -> str:
        """Resuelve rutas de assets tanto en desarrollo como congelado con PyInstaller."""
        if getattr(sys, "frozen", False):
            base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
        return os.path.join(base_dir, "assets", subpath)

    def init_ui(self):
        # Layout raíz horizontal (Sidebar a la izquierda + Contenido a la derecha)
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 1. Barra Lateral (Sidebar) ──────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {self._colors['card']};
                border-right: 1px solid {self._colors['border']};
            }}
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 22, 16, 18)
        sidebar_layout.setSpacing(5)

        # Header del Sidebar (Logo / Título)
        app_title = QLabel("MULTIMEDIA")
        app_title.setStyleSheet(f"""
            color: {self._colors['text_main']};
            font-size: 15pt;
            font-weight: 800;
            letter-spacing: 1px;
            background: transparent;
            border: none;
        """)

        app_subtitle = QLabel("CONVERTER SUITE")
        app_subtitle.setStyleSheet(f"""
            color: {self._colors['text_muted']};
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 2px;
            background: transparent;
            border: none;
            margin-bottom: 12px;
        """)
        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(app_subtitle)

        # Separador
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {self._colors['border']}; border: none;")
        sidebar_layout.addWidget(sep)
        sidebar_layout.addSpacing(6)

        # Botones de Navegación de Herramientas
        nav_items = [
            ("video", t("nav_video"), VideoConverter),
            ("audio", t("nav_audio"), AudioConverter),
            ("image", t("nav_image"), ImageConverter),
            ("compressor", t("nav_compressor"), VideoCompressorUI),
            ("gif_maker", t("nav_gif_maker"), GifMakerUI),
            ("media_cut", t("nav_media_cut"), MediaCutterUI),
            ("booster", t("nav_booster"), AudioBoosterUI),
            ("merger", t("nav_merger"), MediaMergerUI),
            ("rescaler", t("nav_rescaler"), ImageRescaler),
        ]

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        for key, label, widget_cls in nav_items:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {self._colors['text_muted']};
                    text-align: left;
                    padding-left: 12px;
                    border-radius: 8px;
                    font-size: 9.5pt;
                    font-weight: 600;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {self._colors['accent_soft']};
                    color: {self._colors['text_main']};
                }}
                QPushButton:checked {{
                    background-color: {self._colors['accent']};
                    color: #FFFFFF;
                    font-weight: 700;
                }}
            """)

            btn.clicked.connect(lambda checked, k=key, cls=widget_cls: self.switch_view(k, cls))
            self.btn_group.addButton(btn)
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()

        # Botón inferior para Salir
        exit_btn = QPushButton(f"  {t('btn_exit')}")
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setFixedHeight(38)
        exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self._colors['text_muted']};
                text-align: left;
                padding-left: 14px;
                border-radius: 9px;
                font-size: 9.5pt;
                font-weight: 600;
                border: 1px solid {self._colors['border']};
            }}
            QPushButton:hover {{
                background-color: rgba(235, 87, 87, 0.15);
                color: #FF5A5A;
                border-color: rgba(235, 87, 87, 0.4);
            }}
        """)
        exit_btn.clicked.connect(self.close)
        sidebar_layout.addWidget(exit_btn)

        root_layout.addWidget(sidebar)

        # ── 2. Área Principal de Contenido (Stacked Widget) ────────────────────
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"background-color: {self._colors['bg']};")
        root_layout.addWidget(self.stacked_widget)

        # Seleccionar por defecto la primera herramienta (Video)
        if nav_items:
            first_key, _, first_cls = nav_items[0]
            self.nav_buttons[first_key].setChecked(True)
            self.switch_view(first_key, first_cls)

    def switch_view(self, tool_id: str, ToolClass):
        """Cambia suavemente a la herramienta seleccionada en el sidebar."""
        if tool_id not in self.loaded_pages:
            try:
                tool_widget = ToolClass()
                tool_widget.parent_navigator = self
                # Ocultar botones de volver internos si existen
                for btn in tool_widget.findChildren(QPushButton):
                    text = btn.text().lower()
                    if "volver" in text or "←" in text:
                        btn.hide()
                self.stacked_widget.addWidget(tool_widget)
                self.loaded_pages[tool_id] = tool_widget
            except Exception as e:
                QMessageBox.critical(self, "Error al cargar módulo", f"No se pudo cargar la vista:\n{e}")
                return

        self.stacked_widget.setCurrentWidget(self.loaded_pages[tool_id])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
