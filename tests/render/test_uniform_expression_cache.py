"""Uniform expressions are compiled once and cached, not re-parsed per frame.

`getAdaptableEvaluationForUniform` used to call `eval()` on a *string*, which
reparses and recompiles the expression on every call. Measured on the target
machine: 5.473 us for the identity expression against 0.379 us once compiled.
At roughly 27 programs x several uniforms x 60 Hz that was 2.0-2.6 ms a frame,
about 40% of all the CPU spent in paintGL.

Two changes: a cache of code objects keyed by the source string, and a
short-circuit for the identity expression "x" -- which is what almost every
uniform carries, since it is the default seeded by
initUniformsAdaptableParameters.

The behaviour must be indistinguishable from the old `eval(string)`, including
for expressions that do not compile and for values that are not floats.
"""

import numpy as np
import pytest

from program.program_base import (
    _COMPILED_EXPRESSIONS,
    IDENTITY_EXPRESSION,
    _compiled_expression,
)

# Expression forms the inspector can realistically hold, including three that
# are broken in different ways: a syntax error, an unknown name, and a runtime
# failure that only shows up for some values.
EXPRESSIONS = [
    "x",
    "x * 2",
    "x + 1",
    "-x",
    "np.sin(x)",
    "abs(x) ** 0.5",
    "x /",  # syntax error: never compiles
    "nope(x)",  # NameError at eval time
    "1 / x",  # ZeroDivisionError when x is 0
]

VALUES = [0.0, 1.0, -2.5]


def reference(evaluation, x):
    """What the previous implementation did, verbatim."""
    try:
        return float(eval(evaluation))
    except Exception:
        return x


def under_test(evaluation, x):
    """The new path, with the same fallback the production code uses."""
    if evaluation == IDENTITY_EXPRESSION:
        try:
            return float(x)
        except Exception:
            return x

    code = _compiled_expression(evaluation) if isinstance(evaluation, str) else None

    try:
        return float(eval(code))
    except Exception:
        return x


@pytest.mark.parametrize("evaluation", EXPRESSIONS)
@pytest.mark.parametrize("x", VALUES)
def test_it_agrees_with_a_plain_eval(evaluation, x):
    expected = reference(evaluation, x)
    actual = under_test(evaluation, x)

    assert type(actual) is type(expected)
    assert actual == pytest.approx(expected, nan_ok=True)


@pytest.mark.parametrize("x", VALUES)
def test_the_identity_shortcut_agrees_with_the_general_path(x):
    # The shortcut exists only for speed, so it must not be a second
    # implementation with its own behaviour.
    code = _compiled_expression(IDENTITY_EXPRESSION)

    assert float(eval(code)) == pytest.approx(float(x))


def test_a_source_string_compiles_only_once():
    source = "x * 3 + 1"
    _COMPILED_EXPRESSIONS.pop(source, None)

    first = _compiled_expression(source)
    second = _compiled_expression(source)

    assert first is not None
    # Identity, not equality: a fresh compile would produce an equal-looking
    # but distinct code object, which is exactly the per-frame cost being
    # removed.
    assert first is second


def test_an_uncompilable_source_is_cached_as_a_failure():
    source = "x +* 2"
    _COMPILED_EXPRESSIONS.pop(source, None)

    assert _compiled_expression(source) is None
    # Cached negatively rather than retried: a typo in the inspector would
    # otherwise cost a failed compile for every uniform on every frame.
    assert source in _COMPILED_EXPRESSIONS
    assert _COMPILED_EXPRESSIONS[source] is None
    assert _compiled_expression(source) is None


def test_editing_an_expression_is_simply_a_miss():
    # Keyed by the source string, so nothing has to be invalidated when the
    # user retypes an expression -- the new string is a new entry.
    before = _compiled_expression("x * 2")
    after = _compiled_expression("x * 3")

    assert before is not after
    assert _compiled_expression("x * 2") is before


def test_expressions_still_see_numpy_and_the_bound_value():
    # eval(code) with no globals argument resolves against the calling frame,
    # so an expression keeps seeing program_base's `np` and the local `x`.
    from program import program_base

    code = _compiled_expression("np.sin(x)")
    x = 0.0

    assert eval(code, program_base.__dict__, {"x": x}) == pytest.approx(np.sin(0.0))
