import time
import numpy as np
import copy

from node.audio_node_base import AudioNode
from node.node_conf import register_node

def name_to_opcode(name):
    l = [ord(char) for char in name]
    return sum(l)

OP_CODE_INPUTAF = name_to_opcode('input_af')

class InputAudioFeatures():
    def __init__(self):
        self.title = 'Audio Features'

@register_node(OP_CODE_INPUTAF)
class InputAudioNode(AudioNode):
    op_title = "Audio Features"
    op_code = OP_CODE_INPUTAF
    content_label = ""
    content_label_objname = "audio_input_features"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[4])
        self.program = InputAudioFeatures()
        self.eval()

    def render(self, audio_features):
        # ???!
        audio_features["custom_parameters"] = {}
        return audio_features
