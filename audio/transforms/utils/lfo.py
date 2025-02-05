import time

import numpy as np

from node.audio_node_base import AudioNode
from node.node_conf import register_node


def name_to_opcode(name):
    lst = [ord(char) for char in name]
    return sum(lst)


OP_CODE_LFO = name_to_opcode("lfo")


class LFO:
    def __init__(self):
        self.title = "LFO"

    def initParams(self):
        self.transform = {
            "undefined_name": {
                "f0": 1,
                "phi": 0,
                "t": time.time(),
                "amplitude": 0.5,
                "offset": 0.5,
            }
        }

    def updateAudioFeatures(self, af):
        for param_name in self.transform.keys():
            settings = self.transform[param_name]
            f0 = settings["f0"]
            phi = settings["phi"]
            t = settings["t"]
            amplitude = settings["amplitude"]
            offset = settings["offset"]
            lfo_transform = np.cos(f0 * t + phi) * amplitude + offset
            af["custom_parameters"][param_name] = lfo_transform

        return af

    def render(self, af):
        return self.updateAudioFeatures(self, af)


@register_node(OP_CODE_LFO)
class LFONode(AudioNode):
    op_title = "LFO"
    op_code = OP_CODE_LFO
    content_label = ""
    content_label_objname = "audio_lfo"

    def __init__(self, scene):
        super().__init__(scene, inputs=[0], outputs=[4])
        self.program = LFO()
        self.eval()

    def render(self, audio_features):
        input_nodes = self.getAudioInputs()

        if not len(input_nodes):
            return af

        return self.program.render(audio_features)
