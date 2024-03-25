import numpy as np
import pickle


class AudioLogger:
    def __init__(self, log_buffer_size=1000, active=False):
        self.record = active
        self.log_buffer_size = log_buffer_size
        self.information = {}
        self.i = 0
        self.audio = np.zeros((0))

    def update_info(self, chunk, res):
        """
        data : audio flux for this frame
        chunk : info_dict for frame i
        """
        self.audio = np.concatenate((self.audio, chunk))
        for k, v in res.items():
            # TODO DEGUEULASSE CHANGER CA 
            if k == '_bpm_on_kick':
                k = 'on_kick'
            if k == '_on_snare':
                k = 'on_snare'
            if k == '_on_hat':
                k = 'on_hat'
            try:
                if v.shape[0] == 4:
                    new_key_slow = k + '_slow'
                    new_key_mid  = k + '_mid'
                    new_key_fast  = k + '_fast'
                    new_key_instant  = k + '_instaneous'
                    if new_key_slow not in self.information.keys():
                        self.information[new_key_slow] = list()
                        self.information[new_key_slow].append(v[1])
                        self.information[new_key_fast] = list()
                        self.information[new_key_fast].append(v[3])
                        self.information[new_key_mid] = list()
                        self.information[new_key_mid].append(v[2])
                        self.information[new_key_instant] = list()
                        self.information[new_key_instant].append(v[0])
                    else:
                        self.information[new_key_slow].append(v[1])
                        self.information[new_key_fast].append(v[3])
                        self.information[new_key_mid].append(v[2])
                        self.information[new_key_instant].append(v[0])
                    if len(self.information[new_key_slow]) > self.log_buffer_size:
                        self.information[new_key_slow].pop(0)
                        self.information[new_key_fast].pop(0)
                        self.information[new_key_mid].pop(0)
                        self.information[new_key_instant].pop(0)
            except:
                if k not in self.information.keys():
                    self.information[k] = list()
                    self.information[k].append(v)
                else:
                    self.information[k].append(v)
                if len(self.information[k]) > self.log_buffer_size:
                    self.information[k].pop(0)
                #print(len(self.information[k]))

        #self.i += 1
        #if self.i > self.wait:
        #    self.information["audio"] = self.audio
        #    pickle.dump(self.information, open("info.pickle", "wb"))
        #    print("Log saved")
