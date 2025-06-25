import numpy as np
import uuid
from os.path import dirname, basename, isfile, join

LIGHT_MODELS = {}


class InvalidLightRegistration(Exception):
    pass


def register_light_now(op_code, class_reference):
    if op_code in LIGHT_MODELS:
        raise InvalidLightRegistration(
            "Duplicate light registration of '%s'. There is already %s" % op_code,
            LIGHT_MODELS[op_code],
        )
    LIGHT_MODELS[op_code] = class_reference


def register_light(op_code):
    def decorator(original_class):
        register_light_now(op_code, original_class)
        return original_class

    return decorator


def name_to_opcode(name: str):
    return name
