import numpy as np
import copy

from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSlot, pyqtSignal, QObject, QTimer

from audio.audio_pipeline import AudioEngine

from gui.patanode import PataNode
from light.core import LightEngine

import keyboard

class WorkerSignals(QObject):
    finished = pyqtSignal()


class Worker(QRunnable):
    def __init__(self, job_function, *args, **kwargs):
        super().__init__()
        self.job_function = job_function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        self.job_function(*self.args, **self.kwargs)
        self.signals.finished.emit()


class PataShadeApp(PataNode):
    def __init__(self):
        self.audio_engine = AudioEngine()
        self.light_engine = LightEngine()
        super().__init__()
        #keyboard.add_hotkey("enter", self.light_engine.force_strobe.activate_10)
        # Thread Pool
        self.threadpool = QThreadPool(maxThreadCount=5)  # number thread in Pool

        self.initAudioTimer()
        self.initLightTimer()
        self.initShaderQTimer()

        # Features for light new engine
        self._last_main_colors = np.zeros(3)
        self._last_audio_features = np.zeros(3)

        # Audio features parameters
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

        self.start_jobs()

    @property
    def last_main_colors(self):
        return self._last_main_colors

    @last_main_colors.setter
    def last_main_colors(self, v):
        if v is None:
            v = np.zeros(3)

        self._last_main_colors = v

    @property
    def last_audio_features(self):
        return self._last_audio_features

    def setShaderWidget(self, shader_widget):
        self.shader_widget = shader_widget

    def initAudioTimer(self):
        self.audio_engine.start_recording()
        self.audio_timer = QTimer()
        self.audio_timer.timeout.connect(self.start_audio_jobs)

    def initLightTimer(self):
        self.light_timer = QTimer()
        self.light_timer.timeout.connect(self.start_light_jobs)

    def initShaderQTimer(self):
        self.shader_timer = QTimer()
        self.shader_timer.timeout.connect(self.start_shader_jobs)

    # Audio thread
    def start_audio_jobs(self):
        worker = Worker(self.update_audio)
        worker.signals.finished.connect(self.on_audio_job_finished)
        self.threadpool.start(worker)

    def on_audio_job_finished(self):
        self.set_audio_features()

    def update_audio(self):
        self.audio_engine()

    def set_audio_features(self):
        af = copy.deepcopy(self.audio_engine.features)
        try:
            af["on_kick"] = 1 if self.last_kick_count != af["kick_count"] else 0
            af["on_hat"] = 1 if self.last_hat_count != af["hat_count"] else 0
            af["on_snare"] = 1 if self.last_snare_count != af["snare_count"] else 0
            self._last_audio_features = af
        except KeyboardInterrupt as exc:
            raise exc
        except Exception:
            pass

    # Light thread
    def start_light_jobs(self):
        def job():
            self.light_engine.__call__(
                color=self.last_main_colors, audio_features=self.last_audio_features
            )
        worker = Worker(job)
        worker.signals.finished.connect(self.on_light_job_finished)
        self.threadpool.start(worker)

    def on_light_job_finished(self):
#       print("Light Job done")
        pass

    # Shader thread
    def start_shader_jobs(self):
        job = self.shader_widget.update
        worker = Worker(job)
        worker.signals.finished.connect(self.on_shader_job_finished)
        self.threadpool.start(worker)

    def on_shader_job_finished(self):
        pass

    # Multithread
    def start_jobs(self):
        self.audio_timer.start(int(1 / 60 * 1000))
        self.light_timer.start(int(1 / 45 * 1000))
        self.shader_timer.start(int(1 / 60 * 1000))

    def closeEvent(self, event):
        self.audio_timer.stop()
        self.light_timer.stop()
        self.shader_timer.stop()
        super().closeEvent(event)
