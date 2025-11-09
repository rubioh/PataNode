LIGHT_PROGRAMS = {}


def register_light_now(op_code, class_reference):
    if op_code in LIGHT_PROGRAMS:
        raise InvalidProgramRegistration(
            "Duplicate program registration of '%s'. There is already %s" % op_code,
            LIGHT_PROGRAMS[op_code],
        )

    LIGHT_PROGRAMS[op_code] = class_reference


def register_light(op_code):
    def decorator(original_class):
        register_light_now(op_code, original_class)
        return original_class

    return decorator


from node.light_node_base import LightNode
from node.node_conf import register_node


@register_node(123)
class Tata(LightNode):
    op_title = "Tata"
