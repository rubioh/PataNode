class AudioEventTracker:
    def __init__(self):
        self.current_state = dict()
        self.event_features = dict()
        self.kick_count = self.hat_count = self.snare_count = 0

        # On Kick Parameters
        self.smooth_low_treshold = 0.1 * 0.5
        self.dlow_treshold = 0.03 * 0.5  # Smooth low derivative
        self.min_frames_since_kick = 18  # Minimal number of frame between two kick
        self.frames_since_kick = 0
        self.decaying_kick = 0

        # On Hat Parameters
        self.smooth_high_treshold = 0.1
        self.dhigh_treshold = 0.03  # Smooth high derivative
        self.min_frames_since_hat = 9  # Minimal number of frame between two hat
        self.frames_since_hat = 0
        self.decaying_hat = 0

        # On Snare Parameters
        self.decaying_snare = 0

        # Mini Chill parameters
        self.mini_chill = 0
        self.wait_mini_chill = 0

    def get_on_kick(self, bpm):
        amp = 0.5 if bpm > 160 else 1  # For high BPM the threshold needs to be reduce
        if (
            self.current_state["dsmooth_low"] > self.dlow_treshold * amp
            and self.current_state["smooth_low"] > self.smooth_low_treshold * amp
        ) and self.frames_since_kick > self.min_frames_since_kick:
            self.frames_since_kick = 0
            self.decaying_kick = 1
            self.event_features["decaying_kick"] = self.decaying_kick
            self.event_features["_bpm_on_kick"] = 1
            self.kick_count += 1
        else:
            self.frames_since_kick += 1
            self.decaying_kick = max(self.decaying_kick - 1.0 / 25.0, 0.0)
            self.event_features["decaying_kick"] = self.decaying_kick
            self.event_features["_bpm_on_kick"] = 0
        self.event_features["kick_count"] = self.kick_count

    def get_on_hat(self):
        if (
            (self.current_state["smooth_high"] > self.smooth_high_treshold)
            and (self.current_state["dsmooth_high"] > self.dhigh_treshold)
            and (self.frames_since_hat > self.min_frames_since_hat)
        ):
            self.frames_since_hat = 0
            self.decaying_hat = 1
            self.event_features["decaying_hat"] = self.decaying_hat
            self.hat_count += 1
            self.event_features["_on_hat"] = 1
        else:
            self.frames_since_hat += 1
            self.decaying_hat = max(self.decaying_hat - 1.0 / 7.0, 0.0)
            self.event_features["decaying_hat"] = self.decaying_hat
            self.event_features["_on_hat"] = 0
        self.event_features["hat_count"] = self.hat_count

    def get_on_snare(self):
        if (
            self.decaying_kick > 0.8
            and self.decaying_hat >= 0.5
            and self.decaying_snare == 0
        ):
            self.snare_count += 1
            self.decaying_snare = 1
            self.event_features["_on_snare"] = 1
        else:
            self.decaying_snare = max(self.decaying_snare - 1.0 / 25.0, 0.0)
            self.event_features["_on_snare"] = 0
        self.event_features["snare_count"] = self.snare_count
        self.event_features["decaying_snare"] = self.decaying_snare

    def get_mini_chill(self):
        if self.decaying_kick == 0:
            self.wait_mini_chill += 1.0 / 40.0
        else:
            self.wait_mini_chill = 0
        if self.wait_mini_chill > 1:
            self.mini_chill = 1
        else:
            self.mini_chill = 0
        self.event_features["mini_chill"] = self.mini_chill

    def __call__(self, af, bpm=140):
        """
        af : Partial audio dictionnary
        """
        self.current_state = af
        self.get_on_kick(bpm=bpm)
        self.get_on_hat()
        self.get_on_snare()
        self.get_mini_chill()
        return self.event_features
