import numpy as np
import pickle


class AudioLogger:
    def __init__(self, log_buffer_size=1000, active=False):
        self.record = active
        self.log_buffer_size = log_buffer_size
        self.information = {}
        self.i = 0
        self.audio = np.zeros(log_buffer_size*int(1/60*16000))

    def update_info(self, chunk, res):
        """
        data : audio flux for this frame
        chunk : info_dict for frame i
        """
        
        size = self.log_buffer_size
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
                        self.information[new_key_slow] = np.zeros(size)
                        self.information[new_key_slow][-1] = v[1]
                        self.information[new_key_fast] = np.zeros(size)
                        self.information[new_key_fast][-1] = v[3]
                        self.information[new_key_mid] = np.zeros(size)
                        self.information[new_key_mid][-1] = v[2]
                        self.information[new_key_instant] = np.zeros(size)
                        self.information[new_key_instant][-1] = v[0]
                    else:
                        tmp = self.information[new_key_slow]
                        tmp[:-1] = tmp[1:]
                        tmp[-1] = v[1]
                        tmp = self.information[new_key_fast]
                        tmp[:-1] = tmp[1:]
                        tmp[-1] = v[3]
                        tmp = self.information[new_key_mid]
                        tmp[:-1] = tmp[1:]
                        tmp[-1] = v[2]
                        tmp = self.information[new_key_instant]
                        tmp[:-1] = tmp[1:]
                        tmp[-1] = v[0]
            except:
                if k not in self.information.keys():
                    self.information[k] = np.zeros(size)
                    self.information[k][-1] = v
                else:
                    tmp = self.information[k]
                    tmp[:-1] = tmp[1:]
                    tmp[-1] = v
                #print(len(self.information[k]))

        #self.i += 1
        #if self.i > self.wait:
        #    self.information["audio"] = self.audio
        #    pickle.dump(self.information, open("info.pickle", "wb"))
        #    print("Log saved")
