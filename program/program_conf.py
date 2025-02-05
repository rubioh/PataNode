import numpy as np

from os.path import dirname, join


SHADER_PROGRAMS = {} # type: ignore[var-annotated] # FIXME: add type annotation
SQUARE_VERT_PATH = join(dirname(__file__), "base/vertex_base.glsl")


class InvalidProgramRegistration(Exception):
    pass


class LoadingFBOsError(Exception):
    pass


class GLSLImplementationError(Exception):
    pass


class UnuseUniformError(Exception):
    pass


class CTXError(Exception):
    pass


def register_program_now(op_code, class_reference):
    if op_code in SHADER_PROGRAMS:
        raise InvalidProgramRegistration(
            "Duplicate program registration of '%s'. There is already %s" % op_code,
            SHADER_PROGRAMS[op_code],
        )

    SHADER_PROGRAMS[op_code] = class_reference


def register_program(op_code):
    def decorator(original_class):
        register_program_now(op_code, original_class)
        return original_class

    return decorator


def get_square_vertex_data():
    vertices = np.array([(-1, -1), (-1, 1), (1, 1), (1, -1)], dtype="f4")
    indices = np.array([(0, 1, 2), (2, 3, 0)])
    data = [vertices[ind] for triangle in indices for ind in triangle]
    return np.array(data, dtype="f4")


def name_to_opcode(name):
    lst = [ord(char) for char in name]
    return sum(lst)


import program.output
import program.scene
import program.utils
import program.textures
import program.effects
import program.colors
import program.gate
import program.particles
import program.zozo
import program.physarum
import program.led_mapping
import program.map
