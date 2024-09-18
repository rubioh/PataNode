import numpy as np

from gui.patanode import PataNode
from PyQt5.QtCore import QTimer
from program.program_manager import ProgramManager, FBOManager

# from light_new import LightEngine
from audio.audio_pipeline import AudioEngine
from light.light import LightEngine


class PataShade(PataNode):

    def __init__(self):
        self.audio_engine = AudioEngine()
        self.light_engine = LightEngine()
        super().__init__(audio_engine=self.audio_engine)
        self.initAudioTimer()
        self.initLightTimer()

        # Features for light new engine
        self._last_main_colors = np.zeros(3)
        self._last_audio_features = np.zeros(3)
        # Audio features parameters
        self.last_kick_count = self.last_hat_count = self.last_snare_count = 0

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
        self.set_audio_features()
        return self._last_audio_features

    def initAudioTimer(self):
        self.audio_engine.start_recording()
        self.audio_timer = QTimer()
        self.audio_timer.timeout.connect(self.update_audio)
        self.audio_timer.start(int(1 / 60 * 1000))

    def initLightTimer(self):
        self.light_timer = QTimer()
        self.light_timer.timeout.connect(
            lambda: self.light_engine.__call__(
                color=self.last_main_colors, audio_features=self.last_audio_features
            )
        )
        self.light_timer.start(int(1 / 45 * 1000))

    def set_audio_features(self):
        audio_features = self.audio_engine.features
        af = audio_features
        af["on_kick"] = 1 if self.last_kick_count != af["kick_count"] else 0
        af["on_hat"] = 1 if self.last_hat_count != af["hat_count"] else 0
        af["on_snare"] = 1 if self.last_snare_count != af["snare_count"] else 0
        last_kick_count = af["kick_count"]
        last_hat_count = af["hat_count"]
        last_snare_count = af["snare_count"]
        self._last_audio_features = af

    def update_audio(self):
        self.audio_engine()

    def closeEvent(self, event):
        self.light_engine.exit()
        super().closeEvent(event)
