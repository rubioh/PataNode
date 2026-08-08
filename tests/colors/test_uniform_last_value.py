"""The preview reads the value the shader actually got, not the program
attribute -- those differ whenever an Inspector expression or an audio
binding sits in between.

The recording lives beside the uniforms rather than inside them: the
uniforms dict is deepcopied into UniformsLookup._all_bindings and written
straight into the .pn file, so anything stored in it becomes part of the
saved format -- and an ndarray value there makes json.dumps raise.
"""

import json

import numpy as np


def makeHolder(evaluation):
    """ProgramsUniforms is at program/program_base.py:583; the bind loop
    ends with `program[uniform_name] = modified_data`, so a plain dict
    stands in for the moderngl program."""
    from program.program_base import ProgramsUniforms

    holder = ProgramsUniforms.__new__(ProgramsUniforms)
    holder.uniforms = {"": {"frequency": {"param_name": "frequency", "type": None}}}
    holder.last_values = {}
    holder.protected = []
    holder.programs = {"": {}}
    holder.lookup = None

    class FakeParent:
        frequency = 2.5

        def getAdaptableEvaluationForUniform(self, program_name, uniform_name, data):
            return evaluation(data)

    holder.parent = FakeParent()
    return holder


def test_bound_value_is_recorded_beside_the_uniforms():
    # Stands in for an Inspector expression of "x*2".
    holder = makeHolder(lambda data: data * 2)

    holder.bindUniformToProgram(None, program_name="")

    assert holder.last_values[""]["frequency"] == 5.0, (
        "the recorded value must be the one after expression evaluation, "
        "not the raw program attribute"
    )


def test_the_serialized_binding_never_carries_the_recorded_value():
    """getUniformsBinding() deepcopies self.uniforms into _all_bindings,
    which ShaderNode.serialize writes to the scene file. A key added to a
    uniform's info dict silently changes the .pn format for every node."""
    holder = makeHolder(lambda data: data * 2)

    holder.bindUniformToProgram(None, program_name="")
    binding = holder.getUniformsBinding()

    assert "last_value" not in binding._all_bindings[""]["frequency"]
    assert "last_value" not in binding.uniforms[""]["frequency"]


def test_a_numpy_uniform_still_serializes():
    """getAdaptableEvaluationForUniform falls back to the raw value when the
    expression raises, so nodes with vector uniforms (Cube, Pingouin) record
    an ndarray. Inside the binding that makes saving any scene containing
    them fail."""
    holder = makeHolder(lambda data: np.array([1.0, 2.0, 3.0]))

    holder.bindUniformToProgram(None, program_name="")
    binding = holder.getUniformsBinding()

    json.dumps(binding._all_bindings)
