import numpy as np


def next_power_of_2(N):
    return 2 ** (int(np.log2(N)) + 1)


def normalize(wav):
    return wav / np.std(wav)


def energy_bandpass(
    dft, low_hz_treshold=25, high_hz_treshold=20000, sampling_rate=16000
):
    """
    dft : absolute value from the dft of a signal

    """
    # Number of bin
    n_fft = len(dft)
    low_bin = min(n_fft, max(0, int(n_fft / sampling_rate * 2 * low_hz_treshold)))
    high_bin = max(0, min(int(n_fft / sampling_rate * 2 * high_hz_treshold), n_fft))
    energy = np.abs(dft[int(low_bin) : int(high_bin)]).sum() / abs(
        high_bin - low_bin
    )  # usless division since I'm normalizing value after
    return energy


class EnergyTracker:
    def __init__(self, sr=16000):
        self.sr = sr
        self.boost = 1
        self.init_params()

    def init_params(self):
        # Class
        self.keys = [
            "full",
            "low",
            "mid",
            "high",
        ]
        # Normalization parameters
        self.norm = {
            "full": 0.55,
            "low": 10.0,
            "high": 0.25,
            "mid": 1.1,
        }
        # Init bandpass tuple -> (lower frequency, higher frequency)
        self.bp = {
            "full": (0, self.sr // 2),
            "high": (4000, self.sr // 2),
            "low": (0, 200),
            "mid": (300, 1000),
        }

        # Init values to 1 for all the features
        self.instantaneous = {}
        self.slow = {}
        self.mid = {}
        self.fast = {}
        self.smooth = {}
        self.dsmooth = {}
        for k in self.keys:
            self.instantaneous[k] = 1
            self.slow[k] = 1
            self.mid[k] = 1
            self.fast[k] = 1
            self.smooth[k] = 1
            self.dsmooth[k] = 0

    def update_energy(self, dft):
        for key, cutoffs in self.bp.items():
            bp_energy = energy_bandpass(dft, cutoffs[0], cutoffs[1])
            if self.af["mini_chill"]:
                self.norm[key] = 0.99995 * self.norm[key] + 0.00005 * bp_energy
            else:
                self.norm[key] = 0.9995 * self.norm[key] + 0.0005 * bp_energy
            self.instantaneous[key] = bp_energy / self.norm[key]

    def update_time_average_energy(self):
        for key, instant_energy in self.instantaneous.items():
            self.slow[key] = 0.99 * self.slow[key] + 0.01 * instant_energy
            self.mid[key] = 0.95 * self.slow[key] + 0.05 * instant_energy
            self.fast[key] = 0.7 * self.slow[key] + 0.3 * instant_energy

    def update_smooth(self):
        for key in self.keys:
            tmp = np.clip(self.fast[key] - self.slow[key], 0, 100)
            self.dsmooth[key] = tmp - self.smooth[key]
            self.smooth[key] = self.smooth[key] * 0.7 + 0.3 * tmp

    def get_features(self):
        res = {}
        for key in self.keys:
            res[key] = [
                self.instantaneous[key],
                self.slow[key],
                self.mid[key],
                self.fast[key],
            ]
            res["smooth" + "_" + key] = self.smooth[key]
            res["dsmooth" + "_" + key] = self.dsmooth[key]
        res["boost"] = self.boost
        res["on_chill"] = self.on_chill
        return res

    def update_boost(self):
        if self.instantaneous["full"] < 1.0:
            self.boost += 0.001
        else:
            self.boost -= 0.003
        self.boost = np.clip(self.boost, 1, 2)
        return self.boost

    def update_chill(self):
        if self.slow["low"] < 0.8:
            self.on_chill = 1
        else:
            self.on_chill = 0

    def __call__(self, dft, af):
        self.af = af
        self.update_energy(dft)
        self.update_time_average_energy()
        self.update_boost()
        self.update_chill()
        self.update_smooth()
        return self.get_features()
