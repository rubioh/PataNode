"""The preview reads the value the shader actually got, not the program
attribute -- those differ whenever an Inspector expression or an audio
binding sits in between.
"""


def test_bound_value_is_recorded_on_the_uniform_info():
    """ProgramsUniforms is at program/program_base.py:583; the bind loop
    ends with `program[uniform_name] = modified_data`, so a plain dict
    stands in for the moderngl program."""
    from program.program_base import ProgramsUniforms

    holder = ProgramsUniforms.__new__(ProgramsUniforms)
    info = {"param_name": "frequency", "type": "attribute"}
    holder.uniforms = {"": {"frequency": info}}
    holder.protected = []
    holder.programs = {"": {}}

    class FakeParent:
        frequency = 2.5

        def getAdaptableEvaluationForUniform(self, program_name, uniform_name, data):
            # Stands in for an Inspector expression of "x*2".
            return data * 2

    holder.parent = FakeParent()

    holder.bindUniformToProgram(None, program_name="")

    assert info["last_value"] == 5.0, (
        "the recorded value must be the one after expression evaluation, "
        "not the raw program attribute"
    )
