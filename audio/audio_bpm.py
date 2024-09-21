import numpy as np
from collections import deque
import time


class BPM_estimator:
    def __init__(self, momentum=0.5, memory_length=64, max_range=50, N_frame=15):
        # Allow the modification every N_frame
        self.count = 0
        self.N_frame = N_frame
        self.shortterm_bpm = 150  # initialize the bpm
        self.bpm = 150  # initialize longterm bpm

        # time information
        self.tic = time.time()

        # BPM estimator parameters
        self.bpm_min = 100
        self.bpm_max = 200
        self.MAX_RANGE = (
            max_range  # MAX RANGE between the measured bpm and the estimated bpm
        )
        self.gradient_bpm = 0
        self.m = momentum  # Momentum parameter
        self.memory_gradient_bpm = deque(
            maxlen=memory_length
        )  # Memory for the update rule
        self.previous_st_bpm = deque(maxlen=memory_length)  # Memory for the update rule
        self.lr = (
            0.1  # Just a definition (rate of change for the shortterm_bpm modification)
        )
        self.momentum_final = 0.1  # Rate of change for the bpm modification

        # On Tempo Parameters
        self.on_tempo = {
            "on_tempo_q": 0,  # -> One turn in .25 kick
            "on_tempo_h": 0,  # -> One turn in .5 kick
            "on_tempo": 0,  # -> One turn in 1 kick
            "on_tempo2": 0,  # -> One turn in 2 kick
            "on_tempo4": 0,  # -> One turn in 4 kick
            "on_tempo8": 0,
            "on_tempo16": 0,
            "on_tempo32": 0,
        }
        self.multiply_coeff = {
            "on_tempo_q": 4,
            "on_tempo_h": 2,
            "on_tempo": 1,
            "on_tempo2": 0.5,
            "on_tempo4": 0.25,
            "on_tempo8": 0.125,
            "on_tempo16": 0.125 * 0.5,
            "on_tempo32": 0.125 * 0.25,
        }
        self.lfo_on_tempo = {
            "lfo_on_tempo_q": 0,
            "lfo_on_tempo_h": 0,  
            "lfo_on_tempo": 0,  
            "lfo_on_tempo2": 0,  
            "lfo_on_tempo4": 0,  
            "lfo_on_tempo8": 0,
            "lfo_on_tempo16": 0,
            "lfo_on_tempo32": 0,
        }
        self.time = 0.0

    def update_bpm(self, on_kick):
        # if we are on a kick do things
        if on_kick and self.count > self.N_frame:
            bpm = 1 / (time.time() - self.tic) * 60
            # Ensure bpm is in the range (bpm_min, bpm_max)
            if (
                abs(bpm - self.shortterm_bpm) < self.MAX_RANGE
                and bpm > self.bpm_min
                and bpm < self.bpm_max
            ):
                # Calculate update's parameters Adagrad (with momentum) like procedure
                gradient = self.shortterm_bpm - bpm  # Estimated bpm's gradient
                self.gradient_bpm = (
                    self.gradient_bpm * self.m + (1.0 - self.m) * gradient
                )  # Momentum
                self.memory_gradient_bpm.append(self.gradient_bpm)  # Memory gradient
                if len(self.memory_gradient_bpm) > 2:
                    self.lr = 2.0 / (
                        np.std(self.memory_gradient_bpm) + 1.0
                    )  # Adaptative rate
                    self.lr = np.clip(self.lr, 0, 1.0)
                # Update short term BPM
                self.shortterm_bpm = self.shortterm_bpm - self.lr * self.gradient_bpm
                # Finally update shortterm bpm
                self.shortterm_bpm = np.clip(
                    self.shortterm_bpm, self.bpm_min, self.bpm_max
                )

                # List of previous shortterm_bpm estimated
                self.previous_st_bpm.append(self.shortterm_bpm)
                if len(self.previous_st_bpm) > 2:
                    self.momentum_final = np.clip(
                        1.0 / (1e-6 + np.std(self.previous_st_bpm) ** 2) * 2.0, 0.0, 1.0
                    )
                # Momentum on the returned bpm
                self.bpm = (1.0 - self.momentum_final) * self.bpm + (
                    self.momentum_final
                ) * np.mean(self.previous_st_bpm)
            # Reset counting parameters
            self.count = 0
            self.tic = time.time()
        #            print(self.bpm)
        else:
            self.count += 1

    def update_on_tempo(self, on_kick):
        for k in self.on_tempo.keys():
            self.on_tempo[k] -= self.bpm / 60 / 60 * self.multiply_coeff[k]
            self.on_tempo[k] = np.clip(self.on_tempo[k], 0, 1)
            if self.on_tempo[k] <= 0:
                self.on_tempo[k] = 1 + self.on_tempo[k]
            self.lfo_on_tempo["lfo_"+k] = np.cos(self.on_tempo[k]*2.*3.14159)*.5+.5

    def update_time(self):
        self.time += self.bpm / 60.0 * 2.0 * np.pi / 60.0

    def get_features(self):
        features = {}
        features["bpm"] = self.bpm
        features["shortterm_bpm"] = self.shortterm_bpm
        for k, v in self.on_tempo.items():
            features[k] = v
        for k, v in self.lfo_on_tempo.items():
            features[k] = v
        features["time"] = self.time
        return features

    def __call__(self, on_kick, on_chill):
        self.update_bpm(on_kick)
        self.update_on_tempo(on_kick)
        self.update_time()
        return self.get_features()
