import numpy as np
from os.path import dirname, basename, isfile, join

SHADER_PROGRAMS = {}

class InvalidProgramRegistration(Exception): pass
class LoadingFBOsError(Exception): pass
class CTXError(Exception): pass

def register_program_now(op_code, class_reference):
    if op_code in SHADER_PROGRAMS:
        raise InvalidProgramRegistration("Duplicate program registration of '%s'. There is already %s"% op_code, SHADER_PROGRAMS[op_code])
    SHADER_PROGRAMS[op_code] = class_reference


def register_program(op_code):
    def decorator(original_class):
        register_program_now(op_code, original_class)
        return original_class
    return decorator


def get_square_vertex_data():
    vertices = np.array([(-1,-1), (-1,1), (1,1), (1,-1)], dtype='f4')
    indices = np.array([(0,1,2), (2,3,0)])
    data = [vertices[ind] for triangle in indices for ind in triangle]
    return np.array(data, dtype='f4')

def load_program(ctx, vert, frag):
    return ctx.program(vertex_shader=vert, fragment_shader=frag)

def name_to_opcode(name):
    l = [ord(char) for char in name]
    return sum(l)

SQUARE_VERT_PATH = join(dirname(__file__), 'base/vertex_base.glsl')

import program.shader

