import numpy as np
import time
import scipy.fft
import sounddevice as sd
import os
from collections import deque
from .audio_utils import EnergyTracker
from .audio_logger import AudioLogger
from .audio_event import AudioEventTracker
from .audio_bpm import BPM_estimator


class AudioEngine:
    def __init__(self, n_fft=1024, sample_rate=16000, get_log=True):
        # Audio parameters
        self.audio_data = np.zeros(n_fft)
        self.sr = sample_rate
        self.n_fft = n_fft
        self.std = (
            2.5  # origin standard deviation. Vary accross time with a moving average
        )

        # Audio Stream callback
        self.chunk = n_fft // 4
        self.buffer = np.zeros((0))
        self.in_data = deque(maxlen=5)
        self.current_wav_frame = np.zeros(self.chunk)
        self.wav_std = 0.25
        self.queue_callback = True
        device_index = os.environ.get("PATASHADE_INPUT_DEVICE", 0)
        print(sd.query_devices())
        try:
            self._stream = sd.InputStream(
                samplerate=self.sr,
                blocksize=self.chunk if self.queue_callback else 0,
                dtype="float32",
                latency=0,
                channels=1,
                device=int(device_index),
                callback=self.callback,
            )
        except (sd.PortAudioError, ValueError):
            devices = sd.query_devices()
            name = next(
                (d["name"] for d in devices if d["index"] == device_index),
                "<no-such-device>",
            )

            print(f"could not setup an input stream on device `{device_index}': {name}")
            print("set PATASHADE_INPUT_DEVICE to a relevant device index:")
            print(devices)
            print("hint: `export PATASHADE_INPUT_DEVICE=<index>`")
            exit(1)
        

        self.log_buffer_size = 250
        # Tracker, estimator and ML models
        self.logger = AudioLogger(log_buffer_size=self.log_buffer_size, active=get_log)
        self.tracker = AudioEventTracker()
        self.bpm_estimator = BPM_estimator(0.5, 16, 110, 15)
        self.ET = EnergyTracker(sr=self.sr)
        # self.pesto = Pesto.PESTO()

        self.true_bpm = None
        self.previous_length = 0

        self.bpm = 140
        self.mini_chill = 0

        self.tic = 0
    
        self.initFeatures()

    def initFeatures(self):
        self.buffer = np.zeros(2000)
        self.current_chunk = np.zeros(self.chunk)
        self.__call__()
        self.buffer = np.zeros((0))

    def start_recording(self):
        self._stream.start()

    def callback(self, indata, frames, times, status):
        if self.queue_callback:  # With Queue buffer
            self.in_data.append(indata.mean(1))
        else:  # Direct callback
            self.in_data = indata.mean(1)
        self.treatment()

    def treatment(self):
        if self.queue_callback:  # With Queue buffer
            signal = np.array(
                [self.in_data[i] for i in range(len(self.in_data))]
            ).reshape(-1)
            self.current_chunk = signal[: self.chunk]
        else:  # Direct callback
            self.current_chunk = np.array(self.in_data).reshape(-1)
        self.buffer = np.concatenate((self.buffer, self.current_chunk))

    def normalize_dft(self, dft):
        std_new = np.std(np.abs(dft))
        self.std = 0.99999 * self.std + 0.00001 * std_new
        return dft / (self.std + 1e-8)

    def update_buffer(self):
        if self.buffer.shape[0] > 24000:
            self.buffer = np.delete(self.buffer, slice(0, self.n_fft, 1))
            self.previous_length -= self.n_fft

    def reset_bpm(self):
        self.bpm_estimator = BPM_estimator(0.5, 30, 110, 15)
        self.true_bpm = None

    def add_to_features(self, D):
        """
        Inputs:
            D a dictionary of features
        Ouputs: (implicit)
            self.res : dictionary of features
        Update self.res dictionnary with the key,value of D
        """
        for key, value in D.items():
            # value to ndarray with dtype float32 (moderngl compatibility)
            self.features[key] = np.array(value, dtype=np.float32)

    def get_shared_features(self):
        self.bpm = self.features["bpm"]
        self.mini_chill = self.features["mini_chill"]

    def __call__(self):
        # Sleep a bit when recording start
        if len(self.buffer) < self.n_fft:
            time.sleep(0.02)
            return self()

        # Remove usless part of the audio buffer (desature RAM)
        self.update_buffer()
        # Compute discrete Fourier transform from the current chunk and normalize it
        dft = scipy.fft.rfft(self.buffer[-self.n_fft :])
        dft = self.normalize_dft(dft)
        self.fft = dft

        # Computing audio features
        self.features = {}
        self.features["fft"] = np.abs(self.fft)  # First get dft
        self.features["mini_chill"] = self.mini_chill
        self.add_to_features(self.ET(dft, self.features))  # Energy things
        self.add_to_features(self.tracker(self.features, self.bpm))  # Kick, Hat, Snare
        self.add_to_features(
            self.bpm_estimator(self.features["_bpm_on_kick"], self.features["on_chill"])
        )  # BPM, tempo
        # self.add_to_features(self.pesto.get_features(self.buffer, self.features)) # Pitch
        self.features["pitch"] = 0

        # Get shared features for the next iteration
        self.get_shared_features()

        # Logger
        if self.queue_callback:
            self.logger.update_info(self.current_chunk, self.features)
        else:
            self.logger.update_info(self.buffer[self.previous_length :], self.features)
        self.previous_length = self.buffer.shape[0]
        
        return self.features
