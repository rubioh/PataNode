"""AudioEngine must publish a frame's features in one atomic rebind.

The engine runs on a worker thread while the GUI thread reads
``engine.features``. It used to assign an empty dict to ``self.features`` and
then fill it key by key, so a reader sampling in that interval iterated a dict
that was still growing and got ``RuntimeError: dictionary changed size during
iteration``. In ``app.set_audio_features`` that read sits outside the try, and
it runs in a slot invoked from C++, where PyQt aborts the process rather than
propagating -- so the race was a hard crash mid-session.

Building the dict locally and publishing it with a single whole-name
reassignment fixes it: a reader sees either the previous frame's features or
this one's, never a mix.

These are source-level assertions rather than a threaded reproduction because
``AudioEngine.__init__`` opens a sounddevice InputStream and calls ``exit(1)``
when there is no capture device, so it cannot be constructed on a test runner.
What is checked is exactly the property that removes the race, and it fails if
someone reintroduces incremental filling.
"""

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "audio" / "audio_pipeline.py"


def method(name):
    tree = ast.parse(SOURCE.read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node

    raise AssertionError("AudioEngine.%s not found in %s" % (name, SOURCE))


def self_features_stores(node):
    """Every place `self.features` is written inside `node`, by kind."""
    whole_name, subscript = [], []

    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AugAssign)):
            continue

        targets = child.targets if isinstance(child, ast.Assign) else [child.target]

        for target in targets:
            # self.features = ...
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "features"
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                whole_name.append(child.lineno)

            # self.features[...] = ...
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "features"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "self"
            ):
                subscript.append(child.lineno)

    return whole_name, subscript


def test_a_frame_publishes_self_features_exactly_once():
    whole_name, _ = self_features_stores(method("__call__"))

    assert len(whole_name) == 1, (
        "__call__ must publish the frame in a single rebind; found %d assignments "
        "to self.features at lines %s. More than one means a reader can observe "
        "an intermediate state." % (len(whole_name), whole_name)
    )


def test_a_frame_is_never_filled_key_by_key():
    _, subscript = self_features_stores(method("__call__"))

    assert not subscript, (
        "__call__ writes into self.features by subscript at lines %s. That is the "
        "original race: the dict is visible to the GUI thread while it is still "
        "growing. Build a local dict and publish it at the end instead." % subscript
    )


def test_nothing_reads_self_features_after_the_publish():
    """Reading the *previous* frame is fine; reading the one just published is not.

    __call__ legitimately reads self.features near the top to carry _on_kick
    over from the last frame -- that is a read of a fully published dict. What
    must not happen is a read after the rebind, because the only reason to
    reach for the attribute at that point is to keep assembling the frame
    through it, which is the race coming back.
    """
    call = method("__call__")
    whole_name, _ = self_features_stores(call)
    publish_line = whole_name[0]

    late_reads = [
        child.lineno
        for child in ast.walk(call)
        if isinstance(child, ast.Attribute)
        and child.attr == "features"
        and isinstance(child.value, ast.Name)
        and child.value.id == "self"
        and child.lineno > publish_line
    ]

    assert not late_reads, (
        "__call__ touches self.features at lines %s, after publishing it at line "
        "%d. Everything from the publish onwards must use the local dict."
        % (late_reads, publish_line)
    )


@pytest.mark.parametrize("helper", ["add_to_features", "get_shared_features"])
def test_the_helpers_take_the_dict_rather_than_reaching_for_it(helper):
    node = method(helper)
    whole_name, subscript = self_features_stores(node)

    assert not whole_name and not subscript, (
        "%s writes to self.features (lines %s). It has to operate on the dict it "
        "is handed, otherwise __call__'s local dict is not where the frame is "
        "actually built." % (helper, whole_name + subscript)
    )

    assert "features" in [arg.arg for arg in node.args.args], (
        "%s must take the dict being built as a parameter" % helper
    )
