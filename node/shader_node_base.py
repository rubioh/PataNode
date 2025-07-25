import copy
import os
import sys
import time
import traceback

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QLabel, QMessageBox

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_node import Node
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException

from program.program_conf import (
    GLSLImplementationError,
    UnuseUniformError,
    name_to_opcode,
)


DEBUG = False
OP_CODE_MAPPING = name_to_opcode("Mapping")


class ShaderGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 160
        self.height = 74
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10

    def initAssets(self):
        super().initAssets()
        self.icons = QImage("node/icons/status_icons.png")

    def paint(self, painter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        offset = 24.0

        if self.node.isDirty():
            offset = 0.0

        if self.node.isInvalid():
            offset = 48.0

        painter.drawImage(
            QRectF(-10, -10, 24.0, 24.0), self.icons, QRectF(offset, 0, 24.0, 24.0)
        )

    def openDialog(self, msg):
        if isinstance(msg, list):
            msgs = ""

            for m in msg:
                msgs += m
        else:
            msgs = msg
        dialog = QMessageBox()
        dialog.setText(msgs)
        dialog.exec()


class ShaderContent(QDMNodeContentWidget):
    def initUI(self):
        lbl = QLabel(self.node.content_label, self)
        lbl.setObjectName(self.node.content_label_objname)


class ShaderNode(Node):
    icon = ""
    op_code = 0
    op_title = "Undefined"
    content_label = ""
    content_label_objname = "shader_node_bg"

    GraphicsNode_class = ShaderGraphicsNode
    NodeContent_class = ShaderContent

    def __init__(self, scene, inputs=[2, 2], outputs=[1]):
        #       inputs = [0] + inputs
        super().__init__(scene, self.__class__.op_title, inputs, outputs)

        self.value = None  # Using to store output texture reference
        self.program = None
        self._container = None  # GraphContainer reference
        self._win_size = (1920, 1080)

        # Current OpenGL ctx
        self.ctx = scene.ctx

        # It's really important to mark all nodes Dirty by default
        self.markDirty()

        # Evaluation Logics for loop in Graph
        self._evaluate = False
        self._in_evaluation = False
        self.previous_evaluation_time = time.time()

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, value):
        if DEBUG:
            print(
                "ShaderNode::container.setter bind container",
                value,
                "to ShaderNode",
                self.__class__.__name__,
            )

        self._container = value

    @property
    def win_size(self):
        return self._win_size

    @win_size.setter
    def win_size(self, value):
        self._win_size = value

    @property
    def already_called(self):
        return self.program.already_called

    @already_called.setter
    def already_called(self, value: bool):
        if self.program is not None:
            self.program.already_called = value

    @property
    def in_evaluation(self):
        return self._in_evaluation

    @in_evaluation.setter
    def in_evaluation(self, value: bool):
        self._in_evaluation = value

    @property
    def evaluate(self):
        return self._evaluate

    @evaluate.setter
    def evaluate(self, value: bool):
        self._evaluate = value

    def changeWindowSize(self, win_size):
        self.win_size = win_size
        self.reload_program()

    def reload_program(self):
        state = self.serialize()
        if (
            self.content_label_objname == "shader_map_led_2d"
            or self.content_label_objname == "shader_Triforce"
        ):
            program = self.program.__class__(
                ctx=self.scene.ctx,
                win_size=self.win_size,
                light_engine=self.scene.app.light_engine,
            )
        else:
            program = self.program.__class__(ctx=self.scene.ctx, win_size=self.win_size)

        del self.program

        self.program = program

        self.deserialize(state, restore_window_size=False)
        self.markDirty()
        self.eval()

    def getCpuAdaptableParameters(self):
        if self.program is not None:
            return self.program.getCpuAdaptableParameters()

        return None

    def getGpuAdaptableParameters(self):
        if self.program is not None:
            return self.program.getGpuAdaptableParameters()

        return None

    def getUniformsBinding(self):
        if self.program is not None:
            return self.program.getUniformsBinding()

        return None

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    def restoreFBODependencies(self):
        self.program.fbos = None

    def findAndConnectFbos(
        self, win_sizes, components=None, dtypes=None, depth=None, num_textures=None
    ):
        if self.program.fbos is not None:
            # FBOs already connected
            return True

        fbos = self.scene.fbo_manager.getFBO(
            win_sizes, components, dtypes, depth, num_textures
        )

        try:
            self.program.connectFbos(fbos)
        except AssertionError:
            print(
                "Created fbos doesn't match the number of required fbos for %s"
                % self.program.__class__.__name__
            )

            self.grNode.setToolTip("No fbo's found")
            self.markInvalid()
            return False

        return True

    def evalInputNodes(self):
        if DEBUG:
            print("Eval Inputs:", self)

        # TODO: test with several textures
        input_nodes = self.getShaderInputs()

        if not input_nodes:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return None

        textures = []

        for input_node in input_nodes:
            if DEBUG:
                print(f"\t Node: {self} evaluate Input Node {input_node}")

            if input_node.evaluate:
                texture = input_node.program.norender()

                if DEBUG:
                    print(
                        f"\t\t ALREADY EVALUATE Input Node: {input_node} with texture {texture}"
                    )

                textures.append(input_node.program.norender())
            else:
                texture = input_node.eval()

                if DEBUG:
                    print(
                        f"\t\t EVALUATE Input Node: {input_node} with texture {texture}"
                    )

                textures.append(texture)

        if len(textures) != len(self.inputs):
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return None

        return textures

    def getShaderInputs(self):
        sockets = self.inputs
        ins = []

        for i, _ in enumerate(sockets):
            ins += super().getInputs(i)

        return ins

    def evalRendering(self, textures=None):
        try:
            output_texture = self.program.render(textures)

            if DEBUG:
                print(
                    "ShaderNode::evalRendering output_texture is ",
                    output_texture,
                    "from ShaderNode",
                    self,
                    "of class",
                    self.__class__.__name__,
                )

            self.value = output_texture
            return True
        except Exception as e:
            self.grNode.setToolTip("Rendering error")
            self.markInvalid()
            self.grNode.openDialog(traceback.format_exception(e))
            print("Error during rendering")
            self.value = None
            return False

        return True

    def evalImplementation(self):
        if DEBUG:
            print("Eval Implementation:", self)

        # Find and connect required FBOs
        win_sizes, components, dtypes, depth_requirements, num_texture = (
            self.program.getFBOSpecifications()
        )
        success = self.findAndConnectFbos(
            win_sizes, components, dtypes, depth_requirements, num_texture
        )

        if not success:
            return False

        # Eval Input Node
        inputs = []

        for ins in self.inputs:
            if ins.socket_type == 0:  # socket_type 0 means audio_input
                continue

            inputs.append(ins)

        if inputs:
            inputs_texture = self.evalInputNodes()

            if inputs_texture is None:
                return False

            for input_texture in inputs_texture:
                success = self.evalRendering(inputs_texture)
        else:
            success = self.evalRendering()

        # Eval Rendering
        if success:
            self.markInvalid(False)
            self.markDirty(False)
            self.grNode.setToolTip("")
            return True

        return False

    def eval(self):
        if DEBUG:
            print("Eval:", self)

        if not self.isDirty() and not self.isInvalid():
            if DEBUG:
                print(
                    " _> returning cached %s value:" % self.__class__.__name__,
                    self.value,
                )

            return self.value

        self.setInputNodeToInEvaluation()

        try:
            if DEBUG:
                print("Eval Try", self)

            _ = self.evalImplementation()
            return self.value
        except ValueError as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            self.markDescendantsDirty()
        except Exception as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            dumpException(e)

    def setInputNodeToInEvaluation(self):
        self.in_evaluation = True
        self.evaluate = False
        t = time.time()

        if t - self.previous_evaluation_time > 2:
            self.previous_evaluation_time = t
            input_nodes = self.getShaderInputs()

            for node in input_nodes:
                node.setInputNodeToInEvaluation()

            if DEBUG:
                print(f"{self} in evaluation:", self.in_evaluation)
        else:
            self.evaluate = True

    def onInputChanged(self, socket=None):
        if DEBUG:
            print("%s::__onInputChanged" % self.__class__.__name__)

        self.markDirty()
        self.eval()

    def reloadGLSLCode(self):
        if DEBUG:
            print("Program before reloading is: ", self.program.program)

        try:
            self.program.reloadProgramSafely()
            self.markDirty()
            self.grNode.setToolTip("")
            self.eval()
        except GLSLImplementationError as e:
            self.markInvalid()
            self.grNode.setToolTip("Implementation Error")
            self.grNode.openDialog(traceback.format_exception(e))
            self.program.reloadPreviousProgramVersion()
        except UnuseUniformError as e:
            self.markInvalid()
            self.grNode.setToolTip("Unuse Uniform Error")
            self.grNode.openDialog(traceback.format_exception(e))
            self.program.reloadPreviousProgramVersion()

        if DEBUG:
            print("Program after reloading is: ", self.program.program)

    def getGLSLCodePath(self):
        return self.program.getGLSLCodePath()

    def openGLSLInTerminal(self, glsl_path):
        platform = sys.platform

        if platform.startswith("darwin"):
            term_program = os.environ.get("TERM_PROGRAM") or "Apple_Terminal"

            if term_program == "iTerm.app":
                os.system(
                    'osascript -e \'tell app "iTerm2" to create window with default profile command "vim %s"\''
                    % glsl_path
                )
            else:
                os.system(
                    'osascript -e \'tell app "Terminal" to activate\' -e \'tell app "Terminal" to do script "vim %s"\''
                    % glsl_path
                )
        elif platform.startswith("linux"):
            os.system('gnome-terminal --command="vim {}"'.format(glsl_path))
        else:
            print("error: unsupported platform: %s" % platform)

        if DEBUG:
            print("Opening in Vim with file %s" % glsl_path)

    def transform_audio_features(self, audio_features):
        pass

    def render(self, audio_features=None):
        pass

    def serialize(self):
        res = super().serialize()
        res["op_code"] = self.__class__.op_code
        adapt_params = copy.deepcopy(self.getCpuAdaptableParameters())

        if self.__class__.op_code == OP_CODE_MAPPING:
            res["mapping_points"] = self.program.polygons

        if not adapt_params:
            program_params = {}
        else:
            for program in adapt_params.keys():
                program_params = adapt_params[program]

                for uniform in program_params.keys():
                    del program_params[uniform]["eval_function"]["connect"]

        res["cpu_adaptable_parameters"] = adapt_params
        adapt_params = copy.deepcopy(self.getGpuAdaptableParameters())

        if not adapt_params:
            program_params = {}
        else:
            for program in adapt_params.keys():
                program_params = adapt_params[program]

                for uniform in program_params.keys():
                    del program_params[uniform]["eval_function"]["connect"]

        res["gpu_adaptable_parameters"] = adapt_params
        uniforms_binding = self.program.getUniformsBinding()._all_bindings
        res["uniforms_binding"] = uniforms_binding
        res["win_size"] = self.win_size
        return res

    def deserialize(self, data, hashmap={}, restore_id=True, restore_window_size=True):
        res = super().deserialize(data, hashmap, restore_id)

        if "cpu_adaptable_parameters" in data.keys():
            adapt_params = data["cpu_adaptable_parameters"]
            cpu_node_params = self.getCpuAdaptableParameters()

            for program in adapt_params.keys():
                program_params = adapt_params[program]

                for uniform in program_params.keys():
                    eval_func = program_params[uniform]["eval_function"]["value"]
                    cpu_node_params[program][uniform]["eval_function"]["value"] = (
                        eval_func
                    )

        if "gpu_adaptable_parameters" in data:
            adapt_params = data["gpu_adaptable_parameters"]
        else:
            adapt_params = {}
        gpu_node_params = self.getGpuAdaptableParameters()

        for program in adapt_params.keys():
            program_params = adapt_params[program]

            for uniform in program_params.keys():
                eval_func = program_params[uniform]["eval_function"]["value"]
                gpu_node_params[program][uniform]["eval_function"]["value"] = eval_func

        uniforms_binding = data["uniforms_binding"]

        if self.__class__.op_code == OP_CODE_MAPPING:
            self.program.polygons = data["mapping_points"]
        self.program.restoreUniformsBinding(uniforms_binding)

        if DEBUG:
            print("Deserialized ShaderNode '%s'" % self.__class__.__name__, "res:", res)

        if restore_window_size and "win_size" in data.keys():
            self.changeWindowSize(data["win_size"])

        return res


class Utils:
    node_type_reference = "Utils"


class Scene:
    node_type_reference = "Scenes"


class Output:
    node_type_reference = "Outputs"


class Input:
    node_type_reference = "Input"


class Texture:
    node_type_reference = "Textures"


class Effects:
    node_type_reference = "Effects"


class Colors:
    node_type_reference = "Colors"


class Particles:
    node_type_reference = "Particles"


class Gate:
    node_type_reference = "Gate"


class Map:
    node_type_reference = "Mapping"


class Physarum:
    node_type_reference = "Physarum"


class LED:
    node_type_reference = "LED"
