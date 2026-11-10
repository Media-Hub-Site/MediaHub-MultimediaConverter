"""
apps/media_converter/i18n.py
────────────────────────────
Gestor de internacionalización ligero para MediaHub-MultimediaConverter.
"""

import os
import sys
import json
import locale

_CURRENT_LANG = None

STRINGS = {
    "es": {
        "app_title": "Convertidor Multimedia — Media Hub",
        "header_title": "Convertidor Multimedia",
        "header_subtitle": "Suite de conversión y edición",
        "nav_video": "Video",
        "nav_audio": "Audio",
        "nav_image": "Imágenes",
        "nav_compressor": "Compresor Video",
        "nav_gif_maker": "Creador de GIF",
        "nav_media_cut": "Cortador Multimedia",
        "nav_booster": "Amplificador Audio",
        "nav_merger": "Unificador Media",
        "nav_rescaler": "Reescalar Imagen",
        "btn_exit": "Salir",
    },
    "en": {
        "app_title": "Multimedia Converter — Media Hub",
        "header_title": "Multimedia Converter",
        "header_subtitle": "Conversion and editing suite",
        "nav_video": "Video",
        "nav_audio": "Audio",
        "nav_image": "Images",
        "nav_compressor": "Video Compressor",
        "nav_gif_maker": "GIF Maker",
        "nav_media_cut": "Media Cutter",
        "nav_booster": "Audio Booster",
        "nav_merger": "Media Merger",
        "nav_rescaler": "Image Rescaler",
        "btn_exit": "Exit",
    }
}


def get_current_language() -> str:
    global _CURRENT_LANG
    if _CURRENT_LANG:
        return _CURRENT_LANG

    # 1. CLI argument
    for arg in sys.argv[1:]:
        if arg.startswith("--lang="):
            val = arg.split("=", 1)[1].strip().lower()
            if val in ("es", "en"):
                _CURRENT_LANG = val
                return _CURRENT_LANG

    # 2. Environment variables
    for env_var in ("MEDIAHUB_APP_LANG", "MEDIAHUB_LANG", "LANG"):
        val = os.environ.get(env_var, "").lower()
        if val.startswith("es"):
            _CURRENT_LANG = "es"
            return "es"
        elif val.startswith("en"):
            _CURRENT_LANG = "en"
            return "en"

    # 3. Local config_lang.json
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    for cfg in [os.path.join(base_dir, "config_lang.json"), os.path.join(base_dir, "..", "config_lang.json")]:
        if os.path.isfile(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("language")
                    if val in ("es", "en"):
                        _CURRENT_LANG = val
                        return _CURRENT_LANG
            except Exception:
                pass

    # 4. Fallback sistema
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.lower().startswith("es"):
            _CURRENT_LANG = "es"
            return "es"
    except Exception:
        pass

    _CURRENT_LANG = "es"
    return "es"


def t(key: str, **kwargs) -> str:
    lang = get_current_language()
    text = STRINGS.get(lang, STRINGS["es"]).get(key, STRINGS["es"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
