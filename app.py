import copy
import time

import numpy as np
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot

from audio.audio_conf import list_audio_features
from audio.audio_pipeline import AudioEngine
from depth.depth_engine import DepthEngine
from depth.depth_source import make_source_factory
from gui.patanode import PataNode
from light.core import LightEngine
from server.server import PataServer

# from light_new import LightEngine


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
    def __init__(self, args):
        self.args = args
        # Set before super().__init__() builds the shader widget: paintGL
        # consults it to refuse painting a half-constructed application.
        self.render_ready = False
        self.audio_engine = AudioEngine()
        self.light_engine = LightEngine(args)
        # Idle until a Depth Input node acquires it -- no USB traffic for users
        # who never touch depth.
        self.depth_engine = DepthEngine(
            make_source_factory(getattr(args, "depth_source", "orbbec"))
        )
        super().__init__()
        self.server = PataServer(args, self)
        # Thread Pool
        self.threadpool = QThreadPool(maxThreadCount=5)  # number thread in Pool

        self.initAudioTimer()
        self.initLightTimer()
        self.initShaderQTimer()
        if args.server:
            self.initPataserverQTimer()
            self.start_server()
        # Features for light new engine
        self._last_main_colors = np.zeros(3)
        self._last_audio_features = {feature: 0 for feature in list_audio_features}

        # Audio features parameters
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

        # Last: everything paintGL touches now exists, so the shader widget
        # may render. Before this, a paint dispatched during startup (the
        # exposure wait in initShaderWidget pumps the event loop) would abort
        # the process on a missing attribute.
        self.render_ready = True

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

    def start_server(self):
        self.server.start()

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

    def initPataserverQTimer(self):
        self.server_timer = QTimer()
        self.server_timer.timeout.connect(self.start_pataserver_jobs)

    # Audio thread
    def start_audio_jobs(self):
        worker = Worker(self.update_audio)
        worker.signals.finished.connect(self.on_audio_job_finished)
        self.threadpool.start(worker)

    def on_audio_job_finished(self):
        self.set_audio_features()
        if self.session_player is not None:
            self.session_player.tick(self.last_audio_features, time.monotonic())

    def update_audio(self):
        self.audio_engine()

    def set_audio_features(self):
        af = copy.deepcopy(self.audio_engine.features)

        try:
            af["on_kick"] = 1 if self.last_kick_count != af["kick_count"] else 0
            af["on_hat"] = 1 if self.last_hat_count != af["hat_count"] else 0
            af["on_snare"] = 1 if self.last_snare_count != af["snare_count"] else 0
            self.last_kick_count = af["kick_count"]
            self.last_hat_count = af["hat_count"]
            self.last_snare_count = af["snare_count"]
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

    def start_pataserver_jobs(self):
        job = self.server.update
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
        if self.args.server:
            self.server_timer.start(int(1 / 60 * 1000))

    def pauseJobs(self):
        self.audio_timer.stop()
        self.light_timer.stop()
        self.shader_timer.stop()
        if self.args.server:
            self.server_timer.stop()

    def resumeJobs(self):
        self.start_jobs()

    def releaseAppResources(self):
        # Runs only on a committed quit, so this is the place for anything not
        # reversible. Closing the engine in closeEvent instead would also run
        # on a cancelled quit, leaving a live application with a closed camera
        # and a refcount desynchronised from its holders. The timers are
        # stopped earlier, by pauseJobs, because that part must be undoable.
        self.depth_engine.close()
