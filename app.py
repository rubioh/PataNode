from node.patanode import PataNode
from PyQt5.QtCore import QTimer
from program.program_manager import ProgramManager, FBOManager
from audio.audio_pipeline import AudioEngine

class PataShade(PataNode):

    def __init__(self):
        self.audio_engine = AudioEngine()
        super().__init__(audio_engine=self.audio_engine)
        self.initAudioTimer()

    def initAudioTimer(self):
        self.audio_engine.start_recording()
        self.audio_timer = QTimer()
        self.audio_timer.timeout.connect(self.update_audio)
        self.audio_timer.start(int(1/60*1000))

    def update_audio(self):
        self.audio_engine()


