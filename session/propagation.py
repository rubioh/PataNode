"""Propagate an edit forward through later states.

Editing state 3 should be able to fix states 4..N too, but must never
clobber a value a later state deliberately changed. Hence: apply where the
old value still stands, skip and report where it does not.

Pure dict manipulation -- no Qt, no GL, no scene.
"""

import copy

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


class StructuralDiff:
    def __init__(
        self,
        added_nodes,
        removed_node_ids,
        added_edges,
        removed_edge_ids,
        removed_node_baseline_edges=None,
    ):
        self.added_nodes = added_nodes
        self.removed_node_ids = removed_node_ids
        self.added_edges = added_edges
        self.removed_edge_ids = removed_edge_ids
        self.removed_node_baseline_edges = (
            removed_node_baseline_edges
            if removed_node_baseline_edges is not None
            else {}
        )


def _socket_ids_for_node(node: dict) -> set:
    """Extract all socket ids from a node's inputs and outputs."""
    socket_ids = set()
    for socket in node.get("inputs", []):
        if "id" in socket:
            socket_ids.add(socket["id"])
    for socket in node.get("outputs", []):
        if "id" in socket:
            socket_ids.add(socket["id"])
    return socket_ids


def diff_scene_structure(baseline: dict, current: dict) -> StructuralDiff:
    baseline_nodes = _nodes_by_id(baseline)
    current_nodes = _nodes_by_id(current)

    baseline_edges = {e["id"]: e for e in baseline.get("edges", [])}
    current_edges = {e["id"]: e for e in current.get("edges", [])}

    removed_node_ids = set(baseline_nodes) - set(current_nodes)

    # For each removed node, track which baseline edges touched it
    removed_node_baseline_edges = {}
    for node_id in removed_node_ids:
        node = baseline_nodes[node_id]
        socket_ids = _socket_ids_for_node(node)
        touching_edges = set()
        for edge_id, edge in baseline_edges.items():
            if edge.get("start") in socket_ids or edge.get("end") in socket_ids:
                touching_edges.add(edge_id)
        removed_node_baseline_edges[node_id] = touching_edges

    return StructuralDiff(
        added_nodes=[
            node for nid, node in current_nodes.items() if nid not in baseline_nodes
        ],
        removed_node_ids=removed_node_ids,
        added_edges=[
            edge for eid, edge in current_edges.items() if eid not in baseline_edges
        ],
        removed_edge_ids=set(baseline_edges) - set(current_edges),
        removed_node_baseline_edges=removed_node_baseline_edges,
    )


def propagate_structure(
    session, from_index: int, diff: StructuralDiff, apply: bool = True
) -> PropagationOutcome:
    """Push node/edge additions and removals onto states after `from_index`.

    When removing a node, skip if the state built new wiring into it.
    """
    outcome = PropagationOutcome()

    for state_index in range(from_index + 1, len(session.states)):
        scene = session.states[state_index].scene
        nodes_in_scene = {n["id"]: n for n in scene.get("nodes", [])}
        node_ids = set(nodes_in_scene.keys())
        edge_ids = {e["id"] for e in scene.get("edges", [])}
        edges_in_scene = {e["id"]: e for e in scene.get("edges", [])}

        for node in diff.added_nodes:
            if node["id"] in node_ids:
                continue
            if apply:
                scene.setdefault("nodes", []).append(copy.deepcopy(node))
            outcome.applied.append((state_index, "added node %s" % node["id"]))

        for node_id in diff.removed_node_ids:
            if node_id not in node_ids:
                continue

            # Check if this state built new wiring into the removed node
            removed_node = nodes_in_scene[node_id]
            state_socket_ids = _socket_ids_for_node(removed_node)

            # Find edges in the state that touch this node
            touching_edge_ids = set()
            for edge_id, edge in edges_in_scene.items():
                if (
                    edge.get("start") in state_socket_ids
                    or edge.get("end") in state_socket_ids
                ):
                    touching_edge_ids.add(edge_id)

            # Check if any of these edges are new (not in baseline)
            baseline_touching_edges = diff.removed_node_baseline_edges.get(
                node_id, set()
            )
            new_edges = touching_edge_ids - baseline_touching_edges

            if new_edges:
                # State added new wiring, skip removal
                outcome.skipped.append(
                    (
                        state_index,
                        "removed node %s" % node_id,
                        "state wires N new edge(s) into it",
                    )
                )
                continue

            if apply:
                scene["nodes"] = [n for n in scene["nodes"] if n["id"] != node_id]
            outcome.applied.append((state_index, "removed node %s" % node_id))

        for edge in diff.added_edges:
            if edge["id"] in edge_ids:
                continue
            if apply:
                scene.setdefault("edges", []).append(copy.deepcopy(edge))
            outcome.applied.append((state_index, "added edge %s" % edge["id"]))

        for edge_id in diff.removed_edge_ids:
            if edge_id not in edge_ids:
                continue
            if apply:
                scene["edges"] = [e for e in scene["edges"] if e["id"] != edge_id]
            outcome.applied.append((state_index, "removed edge %s" % edge_id))

    return outcome
