import numpy as np
import pickle


class AudioLogger:
    def __init__(self, wait=1000, active=False):
        self.record = active
        self.information = {}
        self.wait = wait
        self.i = 0
        self.audio = np.zeros((0))

    def update_info(self, chunk, res):
        """
        data : audio flux for this frame
        chunk : info_dict for frame i
        """
        if self.i > self.wait or self.i < 0:
            self.i += 1
            return

        self.audio = np.concatenate((self.audio, chunk))
        for k, v in res.items():
            if k not in self.information.keys():
                self.information[k] = list()
                self.information[k].append(v)
            else:
                self.information[k].append(v)

        self.i += 1
        if self.i > self.wait:
            self.information["audio"] = self.audio
            pickle.dump(self.information, open("info.pickle", "wb"))
            print("Log saved")
