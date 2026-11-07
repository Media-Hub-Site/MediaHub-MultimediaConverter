import os
import sys
import subprocess
import tempfile
import wave
import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar, QMessageBox,
    QCheckBox, QRadioButton, QButtonGroup, QComboBox, QFrame,
    QGraphicsDropShadowEffect, QStackedWidget, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint, QSize, QUrl, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QIcon, QMouseEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from apps.media_converter.ui.ui_theme import get_app_colors, apply_window_theme
from apps.media_converter.converters.conversion import _find_ffmpeg

# --- THREADS ---

class WaveformAnalyzerThread(QThread):
    finished_data = pyqtSignal(np.ndarray, float) # waveform array, duration in seconds
    error = pyqtSignal(str)

    def __init__(self, file_path, num_bars=500):
        super().__init__()
        self.file_path = file_path
        self.num_bars = num_bars

    def run(self):
        try:
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                self.error.emit("No se pudo encontrar FFmpeg. Asegúrate de que esté instalado o en FFMPEG_PATH.")
                return

            temp_wav = os.path.join(tempfile.gettempdir(), "temp_waveform.wav")
            
            # Use ffmpeg to convert to 8000Hz mono wav
            cmd = [
                ffmpeg_path, "-y", "-i", self.file_path,
                "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", temp_wav
            ]
            
            # Hide console window on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
            if proc.returncode != 0:
                self.error.emit(f"FFmpeg error: {proc.stderr.decode('utf-8', errors='ignore')}")
                return
            
            import wave
            with wave.open(temp_wav, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_data = wf.readframes(n_frames)
                data = np.frombuffer(raw_data, dtype=np.int16)
            
            duration = len(data) / sample_rate
            
            # Chunk the data
            chunk_size = len(data) // self.num_bars
            if chunk_size == 0:
                chunk_size = 1
                
            waveform = np.zeros(self.num_bars)
            for i in range(self.num_bars):
                start = i * chunk_size
                end = start + chunk_size
                chunk = data[start:end]
                if len(chunk) > 0:
                    waveform[i] = np.max(np.abs(chunk))
            
            # Normalize
            max_val = np.max(waveform)
            if max_val > 0:
                waveform = waveform / max_val
                
            # Clean up
            try:
                os.remove(temp_wav)
            except:
                pass
                
            self.finished_data.emit(waveform, duration)
        except Exception as e:
            self.error.emit(str(e))

class AudioCutWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, input_file, output_file, start_sec, end_sec, total_duration, mode, fade_in, fade_out):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.total_duration = total_duration
        self.mode = mode # 'keep' or 'remove'
        self.fade_in_sec = fade_in
        self.fade_out_sec = fade_out

    def run(self):
        try:
            ffmpeg_path = _find_ffmpeg()
            if not ffmpeg_path:
                self.error.emit("No se pudo encontrar FFmpeg. Asegúrate de que esté instalado o en FFMPEG_PATH.")
                return

            cmd = [ffmpeg_path, "-y", "-i", self.input_file]
            
            filter_complex = []
            audio_map = ""
            
            if self.mode == "keep":
                # Keep inside selection
                duration = self.end_sec - self.start_sec
                af_filters = [f"atrim=start={self.start_sec}:end={self.end_sec}", "asetpts=PTS-STARTPTS"]
                
                if self.fade_in_sec > 0:
                    af_filters.append(f"afade=t=in:ss=0:d={self.fade_in_sec}")
                if self.fade_out_sec > 0:
                    fade_out_start = max(0, duration - self.fade_out_sec)
                    af_filters.append(f"afade=t=out:st={fade_out_start}:d={self.fade_out_sec}")
                
                cmd.extend(["-af", ",".join(af_filters)])
            else:
                # Remove middle (Cut Outside)
                # Part 1: 0 to start_sec
                # Part 2: end_sec to total_duration
                f1 = f"[0:a]atrim=start=0:end={self.start_sec},asetpts=PTS-STARTPTS[p1]"
                f2 = f"[0:a]atrim=start={self.end_sec}:end={self.total_duration},asetpts=PTS-STARTPTS[p2]"
                
                filter_complex.extend([f1, f2])
                
                concat_inputs = "[p1][p2]"
                concat_cmd = f"{concat_inputs}concat=n=2:v=0:a=1[out]"
                
                # Apply fades if needed on the concatenated result
                final_map = "[out]"
                if self.fade_in_sec > 0 or self.fade_out_sec > 0:
                    af_filters = []
                    if self.fade_in_sec > 0:
                        af_filters.append(f"afade=t=in:ss=0:d={self.fade_in_sec}")
                    if self.fade_out_sec > 0:
                        new_dur = self.start_sec + (self.total_duration - self.end_sec)
                        fade_out_start = max(0, new_dur - self.fade_out_sec)
                        af_filters.append(f"afade=t=out:st={fade_out_start}:d={self.fade_out_sec}")
                    
                    filter_complex.append(f"[out] {','.join(af_filters)} [faded]")
                    final_map = "[faded]"
                else:
                    filter_complex.append(concat_cmd)
                    
                if self.fade_in_sec > 0 or self.fade_out_sec > 0:
                    filter_complex.insert(-1, concat_cmd)
                
                cmd.extend(["-filter_complex", ";".join(filter_complex), "-map", final_map])
            
            # Re-encode audio to high quality to preserve it after filtering
            cmd.extend(["-q:a", "0"])
            cmd.append(self.output_file)
            
            self.progress.emit(20)
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
            if proc.returncode != 0:
                self.error.emit(f"Error procesando audio: {proc.stderr.decode('utf-8', errors='ignore')}")
                return
                
            self.progress.emit(100)
            self.finished.emit(self.output_file)
            
        except Exception as e:
            self.error.emit(str(e))


# --- WIDGETS ---

class AudioDropLabel(QLabel):
    def __init__(self, on_file_dropped, parent=None):
        super().__init__(parent)
        self.on_file_dropped = on_file_dropped
        self.setAcceptDrops(True)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            valid = any(
                url.toLocalFile().lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))
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
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                    self.on_file_dropped(file_path)
                    break # Solo permitimos procesar uno a la vez
        else:
            event.ignore()

class WaveformWidget(QWidget):
    selection_changed = pyqtSignal(float, float) # start_sec, end_sec
    seek_requested = pyqtSignal(float) # sec

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.setMouseTracking(True)
        self.colors = get_app_colors()
        
        self.waveform_data = None
        self.duration = 0.0
        
        self.start_ratio = 0.0
        self.end_ratio = 1.0
        
        self.playback_ratio = -1.0 # -1 means not playing
        
        self.dragging = None # 'start' or 'end' or 'center'
        self.drag_offset = 0

    def set_data(self, data, duration):
        self.waveform_data = data
        self.duration = duration
        self.start_ratio = 0.0
        self.end_ratio = 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        
        # Draw background
        painter.fillRect(rect, QColor(self.colors['card']))
        
        if self.waveform_data is None or len(self.waveform_data) == 0:
            painter.setPen(QColor(self.colors['text_muted']))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Cargando espectro de audio...")
            return

        # Draw waveform
        bar_width = w / len(self.waveform_data)
        
        sel_start_px = int(self.start_ratio * w)
        sel_end_px = int(self.end_ratio * w)
        
        for i, val in enumerate(self.waveform_data):
            bar_h = val * h * 0.9
            x = i * bar_width
            y = (h - bar_h) / 2
            
            # Determine color based on selection
            if sel_start_px <= x <= sel_end_px:
                color = QColor(self.colors['accent'])
            else:
                color = QColor(self.colors['text_muted'])
                color.setAlpha(80)
                
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(int(x), int(y), max(1, int(bar_width - 1)), int(bar_h))
            
        # Draw selection borders
        painter.setPen(QPen(QColor(self.colors['accent_hover']), 2))
        painter.drawLine(sel_start_px, 0, sel_start_px, h)
        painter.drawLine(sel_end_px, 0, sel_end_px, h)
        
        # Draw playhead
        if self.playback_ratio >= 0.0:
            playhead_px = int(self.playback_ratio * w)
            painter.setPen(QPen(QColor("#2ECC71"), 3))
            painter.drawLine(playhead_px, 0, playhead_px, h)

    def mousePressEvent(self, event: QMouseEvent):
        if self.duration == 0: return
        w = self.width()
        x = event.position().x()
        
        if event.button() == Qt.MouseButton.RightButton:
            self.dragging = 'playhead'
            self.seek_requested.emit((x / w) * self.duration)
            return
            
        sel_start_px = self.start_ratio * w
        sel_end_px = self.end_ratio * w
        
        handle_tolerance = 10
        if self.playback_ratio >= 0.0 and abs(x - (self.playback_ratio * w)) <= handle_tolerance:
            self.dragging = 'playhead'
            self.seek_requested.emit((x / w) * self.duration)
        elif abs(x - sel_start_px) <= handle_tolerance:
            self.dragging = 'start'
        elif abs(x - sel_end_px) <= handle_tolerance:
            self.dragging = 'end'
        elif sel_start_px < x < sel_end_px:
            self.dragging = 'center'
            self.drag_offset = x - sel_start_px
        else:
            # Clicked outside, jump start handle to here
            self.start_ratio = x / w
            if self.start_ratio >= self.end_ratio:
                self.end_ratio = min(1.0, self.start_ratio + 0.1)
            self.dragging = 'start'
            self.update()
            self._emit_times()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.duration == 0: return
        w = self.width()
        x = max(0, min(w, event.position().x()))
        ratio = x / w
        
        if self.dragging == 'start':
            if ratio < self.end_ratio - 0.01:
                self.start_ratio = ratio
        elif self.dragging == 'end':
            if ratio > self.start_ratio + 0.01:
                self.end_ratio = ratio
        elif self.dragging == 'center':
            width_ratio = self.end_ratio - self.start_ratio
            new_start = (x - self.drag_offset) / w
            new_start = max(0, min(1.0 - width_ratio, new_start))
            self.start_ratio = new_start
            self.end_ratio = new_start + width_ratio
        elif self.dragging == 'playhead':
            self.seek_requested.emit((x / w) * self.duration)
            
        if self.dragging and self.dragging != 'playhead':
            self.update()
            self._emit_times()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = None
        
    def _emit_times(self):
        self.selection_changed.emit(self.start_ratio * self.duration, self.end_ratio * self.duration)


class AudioCutUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cortador de Audio Avanzado")
        self.setGeometry(100, 100, 800, 550)
        apply_window_theme(self)
        self.colors = get_app_colors()
        
        self.input_file = None
        self.total_duration = 0.0
        self.start_sec = 0.0
        self.end_sec = 0.0
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Title
        title = QLabel("Cortador de Audio Avanzado")
        title.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {self.colors['text_main']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Drop Zone
        self.drop_label = AudioDropLabel(self.load_audio)
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setText("Arrastra un archivo de audio o haz clic para seleccionar")
        self.drop_label.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {self.colors['border']};
                border-radius: 10px;
                background-color: {self.colors['card']};
                color: {self.colors['text_muted']};
                padding: 20px;
            }}
            QLabel:hover {{
                border-color: {self.colors['accent']};
                color: {self.colors['accent']};
            }}
        """)
        self.drop_label.mousePressEvent = lambda e: self.browse_file()
        main_layout.addWidget(self.drop_label)
        
        # Waveform
        self.waveform = WaveformWidget()
        self.waveform.selection_changed.connect(self.on_selection_changed)
        self.waveform.seek_requested.connect(self.seek_player)
        main_layout.addWidget(self.waveform)
        
        # Time Labels
        time_layout = QHBoxLayout()
        self.lbl_start = QLabel("Inicio: 00:00.00")
        self.lbl_end = QLabel("Fin: 00:00.00")
        self.lbl_start.setStyleSheet(f"color: {self.colors['text_main']}; font-weight: bold;")
        self.lbl_end.setStyleSheet(f"color: {self.colors['text_main']}; font-weight: bold;")
        time_layout.addWidget(self.lbl_start)
        time_layout.addStretch()
        time_layout.addWidget(self.lbl_end)
        main_layout.addLayout(time_layout)
        
        # Playback Controls
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_player_position_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)
        
        self.playing_selection = False
        
        playback_layout = QHBoxLayout()
        self.btn_play_sel = QPushButton("▶ Previsualizar")
        self.btn_play_all = QPushButton("▶ Desde el Inicio")
        self.btn_resume = QPushButton("▶ Reanudar")
        self.btn_pause = QPushButton("⏸ Pausar")
        
        for btn in [self.btn_play_sel, self.btn_play_all, self.btn_resume, self.btn_pause]:
            btn.setStyleSheet(f"QPushButton {{ background: {self.colors['bg']}; color: {self.colors['text_main']}; border-radius: 5px; padding: 6px; border: 1px solid {self.colors['border']}; }} QPushButton:hover {{ background: {self.colors['accent_soft']}; }}")
            btn.setEnabled(False)
            playback_layout.addWidget(btn)
            
        self.btn_play_sel.clicked.connect(self.play_selection)
        self.btn_play_all.clicked.connect(self.play_all)
        self.btn_resume.clicked.connect(self.player.play)
        self.btn_pause.clicked.connect(self.player.pause)
        
        main_layout.addLayout(playback_layout)
        
        # Controls Frame
        controls_frame = QFrame()
        controls_frame.setStyleSheet(f"background: {self.colors['card']}; border-radius: 10px;")
        controls_layout = QHBoxLayout(controls_frame)
        
        # Options Left
        opt_left_layout = QVBoxLayout()
        
        def make_fade_row(title):
            row = QHBoxLayout()
            chk = QCheckBox(title)
            chk.setStyleSheet(f"color: {self.colors['text_main']};")
            spin = QDoubleSpinBox()
            spin.setRange(0.5, 10.0)
            spin.setSingleStep(0.5)
            spin.setValue(2.0)
            spin.setSuffix("s")
            spin.setEnabled(False)
            spin.setStyleSheet(f"background: {self.colors['bg']}; color: {self.colors['text_main']}; border: 1px solid {self.colors['border']}; border-radius: 3px;")
            chk.toggled.connect(spin.setEnabled)
            row.addWidget(chk)
            row.addWidget(spin)
            row.addStretch()
            return row, chk, spin
            
        row_in, self.check_fade_in, self.spin_fade_in = make_fade_row("Fade In")
        row_out, self.check_fade_out, self.spin_fade_out = make_fade_row("Fade Out")
        
        opt_left_layout.addLayout(row_in)
        opt_left_layout.addLayout(row_out)
        controls_layout.addLayout(opt_left_layout)
        
        # Options Right (Radio Buttons)
        opt_right_layout = QVBoxLayout()
        self.radio_keep = QRadioButton("Mantener Selección")
        self.radio_remove = QRadioButton("Eliminar Selección (Cortar medio)")
        self.radio_keep.setChecked(True)
        self.radio_keep.setStyleSheet(f"color: {self.colors['text_main']};")
        self.radio_remove.setStyleSheet(f"color: {self.colors['text_main']};")
        
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.radio_keep)
        self.mode_group.addButton(self.radio_remove)
        
        opt_right_layout.addWidget(self.radio_keep)
        opt_right_layout.addWidget(self.radio_remove)
        controls_layout.addLayout(opt_right_layout)
        
        # Format Combo
        format_layout = QVBoxLayout()
        format_lbl = QLabel("Formato Salida:")
        format_lbl.setStyleSheet(f"color: {self.colors['text_muted']};")
        self.combo_format = QComboBox()
        self.combo_format.addItems([".mp3", ".wav", ".m4a"])
        self.combo_format.setStyleSheet(f"background: {self.colors['bg']}; color: {self.colors['text_main']}; border: 1px solid {self.colors['border']}; border-radius: 5px; padding: 5px;")
        format_layout.addWidget(format_lbl)
        format_layout.addWidget(self.combo_format)
        controls_layout.addLayout(format_layout)
        
        main_layout.addWidget(controls_frame)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        self.btn_back = QPushButton("Volver")
        self.btn_back.setStyleSheet(f"QPushButton {{ background: {self.colors['card']}; color: {self.colors['text_main']}; border-radius: 8px; padding: 10px; }}")
        self.btn_back.clicked.connect(self.go_back)
        
        self.btn_process = QPushButton("Cortar Audio")
        self.btn_process.setStyleSheet(f"QPushButton {{ background: {self.colors['accent']}; color: #fff; font-weight: bold; border-radius: 8px; padding: 10px; }} QPushButton:hover {{ background: {self.colors['accent_hover']}; }}")
        self.btn_process.clicked.connect(self.process_audio)
        self.btn_process.setEnabled(False)
        
        bottom_layout.addWidget(self.btn_back)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_process)
        
        main_layout.addLayout(bottom_layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Audio", "", "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg)")
        if file_path:
            self.load_audio(file_path)

    def load_audio(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.flac', '.ogg']:
            reply = QMessageBox.warning(
                self, 
                "Formato no soportado por el reproductor",
                f"El formato {ext} puede no ser reproducible nativamente. Para previsualizarlo correctamente, te sugerimos convertirlo primero a .mp3 o .wav.\n\n¿Deseas ir al Convertidor de Audio ahora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                from apps.media_converter.ui.audio_converter import AudioConverter
                self.converter = AudioConverter()
                self.converter.show()
                # Pasar el archivo al convertidor si fuera posible, pero AudioConverter usa on_file_dropped
                self.converter.on_file_dropped([file_path])
                self.close()
                return
        
        self.input_file = file_path
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.drop_label.setText(f"Cargando: {os.path.basename(file_path)}...")
        self.btn_process.setEnabled(False)
        for btn in [self.btn_play_sel, self.btn_play_all, self.btn_resume, self.btn_pause]:
            btn.setEnabled(False)
        
        # Analyze Waveform
        self.analyzer = WaveformAnalyzerThread(file_path)
        self.analyzer.finished_data.connect(self.on_waveform_loaded)
        self.analyzer.error.connect(self.on_error)
        self.analyzer.start()

    def on_waveform_loaded(self, data, duration):
        self.total_duration = duration
        self.drop_label.setText(f"Archivo: {os.path.basename(self.input_file)}")
        self.waveform.set_data(data, duration)
        self.btn_process.setEnabled(True)
        for btn in [self.btn_play_sel, self.btn_play_all, self.btn_resume, self.btn_pause]:
            btn.setEnabled(True)
        self.on_selection_changed(0, duration)

    def format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{int(m):02d}:{s:05.2f}"

    def on_selection_changed(self, start_sec, end_sec):
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.lbl_start.setText(f"Inicio: {self.format_time(start_sec)}")
        self.lbl_end.setText(f"Fin: {self.format_time(end_sec)}")
        
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.waveform.playback_ratio = -1.0
            self.waveform.update()

    def play_selection(self):
        self.playing_selection = True
        self.player.setPosition(int(self.start_sec * 1000))
        self.player.play()

    def play_all(self):
        self.playing_selection = False
        self.player.setPosition(0)
        self.player.play()

    def seek_player(self, sec):
        self.player.setPosition(int(sec * 1000))
        self.waveform.playback_ratio = sec / self.total_duration
        self.waveform.update()

    def on_player_position_changed(self, position):
        if self.total_duration <= 0:
            return
            
        t = position / 1000.0
        self.waveform.playback_ratio = t / self.total_duration
        self.waveform.update()
        
        mode = "keep" if self.radio_keep.isChecked() else "remove"
        fade_in_sec = self.spin_fade_in.value() if self.check_fade_in.isChecked() else 0.0
        fade_out_sec = self.spin_fade_out.value() if self.check_fade_out.isChecked() else 0.0
        
        vol = 1.0
        
        if mode == "keep":
            if self.playing_selection and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                if t >= self.end_sec:
                    self.player.pause()
                    self.waveform.playback_ratio = -1.0
                    self.waveform.update()
                    return
                    
            if self.start_sec <= t <= self.end_sec:
                if fade_in_sec > 0 and t < self.start_sec + fade_in_sec:
                    vol = (t - self.start_sec) / fade_in_sec
                if fade_out_sec > 0 and t > self.end_sec - fade_out_sec:
                    vol = min(vol, (self.end_sec - t) / fade_out_sec)
        
        elif mode == "remove":
            # Salto en tiempo real para previsualizar el corte del medio
            if self.playing_selection and self.start_sec <= t < self.end_sec - 0.1:
                self.player.setPosition(int(self.end_sec * 1000))
                return
                
            if fade_in_sec > 0 and t < fade_in_sec:
                vol = t / fade_in_sec
            if fade_out_sec > 0 and t > self.total_duration - fade_out_sec:
                vol = min(vol, (self.total_duration - t) / fade_out_sec)

        self.audio_output.setVolume(max(0.0, min(1.0, vol)))

    def on_playback_state_changed(self, state):
        if state != QMediaPlayer.PlaybackState.PlayingState:
            # Optionally hide the playhead when paused/stopped
            pass

    def process_audio(self):
        if not self.input_file:
            return
            
        ext = self.combo_format.currentText()
        out_path, _ = QFileDialog.getSaveFileName(self, "Guardar Audio Cortado", f"audio_cortado{ext}", f"Audio File (*{ext})")
        if not out_path:
            return
            
        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        
        mode = "keep" if self.radio_keep.isChecked() else "remove"
        fade_in = self.spin_fade_in.value() if self.check_fade_in.isChecked() else 0.0
        fade_out = self.spin_fade_out.value() if self.check_fade_out.isChecked() else 0.0
        
        self.worker = AudioCutWorker(
            self.input_file, out_path, self.start_sec, self.end_sec, 
            self.total_duration, mode, fade_in, fade_out
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_process_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_process_finished(self, out_path):
        self.btn_process.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Éxito", f"El audio ha sido cortado correctamente:\n{out_path}")

    def on_error(self, err_msg):
        self.btn_process.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.drop_label.setText("Arrastra un archivo de audio o haz clic para seleccionar")
        QMessageBox.critical(self, "Error", f"Se produjo un error:\n{err_msg}")

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
