"""Propagate an edit forward through later states.

Editing state 3 should be able to fix states 4..N too, but must never
clobber a value a later state deliberately changed. Hence: apply where the
old value still stands, skip and report where it does not.

Pure dict manipulation -- no Qt, no GL, no scene.
"""

PARAM_KINDS = {"cpu": "cpu_adaptable_parameters", "gpu": "gpu_adaptable_parameters"}


class ParamChange:
    def __init__(self, node_id, kind, program, uniform, old_value, new_value):
        self.node_id = node_id
        self.kind = kind
        self.program = program
        self.uniform = uniform
        self.old_value = old_value
        self.new_value = new_value

    def __repr__(self):
        return "<ParamChange node=%s %s.%s.%s %r -> %r>" % (
            self.node_id,
            self.kind,
            self.program,
            self.uniform,
            self.old_value,
            self.new_value,
        )

    def __eq__(self, other):
        return isinstance(other, ParamChange) and vars(self) == vars(other)


class PropagationOutcome:
    def __init__(self, applied=None, skipped=None):
        self.applied = applied if applied is not None else []
        self.skipped = skipped if skipped is not None else []


def _nodes_by_id(scene: dict) -> dict:
    return {node["id"]: node for node in scene.get("nodes", [])}


def _values(node: dict, kind: str):
    """Yield (program, uniform, value) for one parameter kind."""
    container = node.get(PARAM_KINDS[kind], {}) or {}
    for program, uniforms in container.items():
        for uniform, spec in uniforms.items():
            yield program, uniform, spec.get("eval_function", {}).get("value")


def _find_value(node: dict, kind: str, program: str, uniform: str):
    container = node.get(PARAM_KINDS[kind], {}) or {}
    spec = container.get(program, {}).get(uniform)
    if spec is None:
        return None, False
    return spec.get("eval_function", {}).get("value"), True


def _set_value(node: dict, kind: str, program: str, uniform: str, value) -> None:
    node[PARAM_KINDS[kind]][program][uniform]["eval_function"]["value"] = value


def diff_scene_params(baseline: dict, current: dict) -> list:
    """Every parameter whose value differs between two scene snapshots."""
    baseline_nodes = _nodes_by_id(baseline)
    changes = []

    for node_id, current_node in _nodes_by_id(current).items():
        baseline_node = baseline_nodes.get(node_id)
        if baseline_node is None:
            continue

        for kind in PARAM_KINDS:
            for program, uniform, new_value in _values(current_node, kind):
                old_value, found = _find_value(baseline_node, kind, program, uniform)
                if found and old_value != new_value:
                    changes.append(
                        ParamChange(
                            node_id, kind, program, uniform, old_value, new_value
                        )
                    )

    return changes


def propagate_params(
    session, from_index: int, changes: list, apply: bool = True
) -> PropagationOutcome:
    """Push `changes` onto states after `from_index`.

    Applies where the state still holds the old value; skips where it
    diverged. `apply=False` previews without mutating anything, so the
    preview and the commit can never disagree.
    """
    outcome = PropagationOutcome()

    for state_index in range(from_index + 1, len(session.states)):
        nodes = _nodes_by_id(session.states[state_index].scene)

        for change in changes:
            node = nodes.get(change.node_id)
            if node is None:
                continue

            actual, found = _find_value(
                node, change.kind, change.program, change.uniform
            )
            if not found:
                continue

            if actual == change.old_value:
                if apply:
                    _set_value(
                        node,
                        change.kind,
                        change.program,
                        change.uniform,
                        change.new_value,
                    )
                outcome.applied.append((state_index, change))
            else:
                outcome.skipped.append((state_index, change, actual))

    return outcome
