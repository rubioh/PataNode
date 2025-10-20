import librosa
import numpy as np
import scipy


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
            "very_low",
            "mid",
            "high",
            #           "50_100",
            #           "100_150",
            #           "150_200",
            #           "200_250",
            #           "250_300",
            #           "300_350",
        ]
        # Normalization parameters
        self.norm = {
            "full": 0.55,
            "low": 10.0,
            "very_low": 5.0,
            "high": 0.25,
            "mid": 1.1,
            #           "50_100": 1,
            #           "100_150": 1,
            #           "150_200": 1,
            #           "200_250": 1,
            #           "250_300": 1,
            #           "300_350": 1,
        }
        # Init bandpass tuple -> (lower frequency, higher frequency)
        self.bp = {
            "full": (0, self.sr // 2),
            "high": (4000, self.sr // 2),
            "very_low": (60, 200),
            "low": (0, 200),
            "mid": (300, 1000),
            #           "50_100" : (50,100),
            #           "100_150" : (100, 150),
            #           "150_200": (150,200),
            #           "200_250": (200,250),
            #           "250_300": (250,300),
            #           "300_350": (300,350),
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

        # Smooth Low DFT things
        self.dft = np.ones((513, 300)) * 1e-8

        freqs = np.array([i * 8000 / 513 for i in range(513)])
        a_weighting = np.clip(librosa.A_weighting(freqs) + 10, 0.1, 20)
        self.a_weighting_filters = np.log(a_weighting) - 0.1
        self.b_weighting_filters = -librosa.B_weighting(
            np.array([i * 8000 / 513 for i in range(513)])
        )
        self.c_weighting_filters = -librosa.C_weighting(
            np.array([i * 8000 / 513 for i in range(513)])
        )
        self.d_weighting_filters = -librosa.D_weighting(
            np.array([i * 8000 / 513 for i in range(513)])
        )
        self.a_weighting = 0.0
        self.b_weighting = 0.0
        self.c_weighting = 0.0
        self.d_weighting = 0.0

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

    def update_a_weighting(self, dft):
        return  # TODO DETECT CE PUTAIN DE KICK JPP GENTLE GRIT MPEG BABY ROLLEN REMIX

    #       current_a_weighting = (self.a_weighting_filters * dft).sum()
    #       self.a_weighting = self.a_weighting * 0.5 + current_a_weighting * 0.5
    #       current_b_weighting = (self.b_weighting_filters * dft).sum()
    #       self.b_weighting = self.b_weighting * 0.5 + current_b_weighting * 0.5
    #       current_c_weighting = (self.c_weighting_filters * dft).sum()
    #       self.c_weighting = self.c_weighting * 0.5 + current_c_weighting * 0.5
    #       current_d_weighting = (self.d_weighting_filters * dft).sum()
    #       self.d_weighting = self.d_weighting * 0.5 + current_d_weighting * 0.5

    def update_smooth(self):
        for key in self.keys:
            #           prev_d = self.dsmooth[key]
            tmp = np.clip(self.fast[key] - self.slow[key], 0, 100)

            # SMOOTH FEATURE
            self.smooth[key] = self.smooth[key] * 0.7 + 0.3 * tmp

            # DSMOOTH FEATURE
            self.dsmooth[key] = np.clip(tmp - self.smooth[key], 0, 10)

    def update_smooth_dft(self):
        self.smooth_low_all[:-1] = self.smooth_low_all[1:]
        self.smooth_low_all[-1] = self.smooth["low"]
        final = self.smooth_low_all - np.mean(self.smooth_low_all)
        self.smooth_dft = np.abs(scipy.fftpack.fft(final))

    #       arg = np.argmax(self.smooth_dft)

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
        res["a_weighting"] = self.a_weighting
        res["b_weighting"] = self.b_weighting
        res["c_weighting"] = self.c_weighting
        res["d_weighting"] = self.d_weighting
        #       res['high_low'] = self.smooth['low'] * self.instantaneous['high']
        #       res["smooth_dft"] = self.smooth_dft[:self.n_fft//8]
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

    def __call__(self, dft, af, audio=None):
        self.audio = audio
        self.af = af
        self.current_dft = np.copy(dft)
        self.update_energy(dft)
        self.update_time_average_energy()
        self.update_boost()
        self.update_chill()
        self.update_smooth()
        self.update_a_weighting(dft)
        return self.get_features()
