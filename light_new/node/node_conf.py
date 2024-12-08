from node.audio_node_base import AudioNode
from node.graph_container_node import GraphContainerNode
from node.shader_node_base import ShaderNode


LISTBOX_MIMETYPE = "application/x-item"

SHADER_NODES = {} # type: ignore[var-annotated] # FIXME: add type annotation

AUDIO_NODES = {} # type: ignore[var-annotated] # FIXME: add type annotation

GRAPH_CONTAINER_OPCODE = 666


class ConfException(Exception):
    pass


class InvalidNodeRegistration(ConfException):
    pass


class OpCodeNotRegistered(ConfException):
    pass


def register_node_now(op_code, class_reference):
    if op_code in SHADER_NODES:
        raise InvalidNodeRegistration(
            "Duplicate node registration of '%s'. There is already %s"
            % (op_code, SHADER_NODES[op_code])
        )

    if op_code in AUDIO_NODES:
        raise InvalidNodeRegistration(
            "Duplicate node registration of '%s'. There is already %s"
            % (op_code, AUDIO_NODES[op_code])
        )

    if ShaderNode in class_reference.__mro__:
        SHADER_NODES[op_code] = class_reference

    if AudioNode in class_reference.__mro__:
        AUDIO_NODES[op_code] = class_reference

    if GraphContainerNode in class_reference.__mro__:
        GRAPH_CONTAINER_NODES[op_code] = class_reference # FIXME: GRAPH_CONTAINER_NODES is not defined


def register_node(op_code):
    def decorator(original_class):
        register_node_now(op_code, original_class)
        return original_class

    return decorator


def get_class_from_opcode(op_code):
    if op_code in SHADER_NODES:
        return SHADER_NODES[op_code]
    if op_code in AUDIO_NODES:
        return AUDIO_NODES[op_code]
    if op_code == GRAPH_CONTAINER_OPCODE:
        return GraphContainerNode
    else:
        raise OpCodeNotRegistered("OpCode '%d' is not registered" % op_code)


# Import all nodes and register them
import program.scene # noqa: E402
import program.output # noqa: E402
import program.utils # noqa: F401, E402
import audio.transforms # noqa: F401, E402

#print(SHADER_NODES)
