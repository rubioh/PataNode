import time
import numpy as np
import copy

from node.audio_node_base import AudioNode
from node.node_conf import register_node

def name_to_opcode(name):
    l = [ord(char) for char in name]
    return sum(l)

OP_CODE_SCALER = name_to_opcode('scaler')

class Scaler():
    def __init__(self):
        self.title = 'Scaler'

    def initParams(self):
        self.transform = {
            "undefined_name": {
                "in_offset": 0,
                "scale": 1,
                "pow": 1,
                "out_offset": 0,
                "to_transform": "smooth_low"
            }
        }

    def updateAudioFeatures(self, af):
        for param_name in self.transform.keys():
            settings = self.transform[param_name]
            in_offset = settings["in_offset"]
            out_offset = settings["out_offset"]
            pow_ = settings["pow"]
            scale = settings["scale"]
            to_transform = af[settings["smooth_low"]]
            scaler_transform = ((to_transform+in_offset)*scale)**pow_ + out_offset
            af["custom_parameters"][param_name] = scaler_transform
        return af

    def render(self, af):
        return self.updateAudioFeatures(self, af)

@register_node(OP_CODE_SCALER)
class ScalerNode(AudioNode):
    op_title = "Scaler"
    op_code = OP_CODE_SCALER
    content_label = ""
    content_label_objname = "audio_scaler"

    def __init__(self, scene):
        super().__init__(scene, inputs=[0], outputs=[4])
        self.program = Scaler()
        self.eval()

    def render(self, audio_features):
        input_nodes = self.getAudioInputs()
        if not len(input_nodes):
            return af
        return self.program.render(audio_features)
