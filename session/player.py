"""Drives a live session against a scene.

Union model: every node any state uses is instantiated once at load, so all
GLSL compiles up front. A state then only rewires edges and applies
parameter values -- no construction, no compilation, no hitch mid-set.
"""

import copy

from nodeeditor.node_edge import Edge
from session.validation import Finding, validate_session


class SessionPlayer:
    def __init__(self, scene, on_status=None, on_evaluate=None):
        self.scene = scene
        self.on_status = on_status or (lambda message: None)
        # Scene has no back-reference to its subwindow, so the render pull
        # has to be handed in. GUI passes editor.doEvalOutputs.
        self.on_evaluate = on_evaluate or (lambda: None)

        self.session = None
        self.current_index = -1
        self.findings = []

    def load(self, session, known_opcodes: set, known_features: set) -> list:
        """Instantiate the union and return every problem found.

        This is the slow step: it compiles every shader the session uses.
        """
        self.session = session
        self.current_index = -1
        self.findings = validate_session(session, known_opcodes, known_features)

        union = session.compute_union()
        union_scene = {
            "id": self.scene.id,
            "scene_width": self.scene.scene_width,
            "scene_height": self.scene.scene_height,
            # deepcopy: Node.deserialize sorts data["inputs"] in place
            # (nodeeditor/node_node.py:628) and would corrupt the session.
            "nodes": copy.deepcopy(union),
            "edges": [],
        }

        self.scene.deserialize(union_scene)

        for message in self.scene.deserialization_errors:
            self.findings.append(Finding(-1, "node", message))

        return self.findings

    # -- transport --------------------------------------------------------

    def goTo(self, index: int) -> bool:
        """Switch to state `index`. All-or-nothing.

        Resolves everything against a staging structure first, so a failure
        leaves the scene untouched on the state it was already showing.
        """
        if self.session is None or not (0 <= index < len(self.session.states)):
            return False

        state = self.session.states[index]

        # deepcopy: Node.deserialize sorts data["inputs"] in place
        # (nodeeditor/node_node.py:628).
        scene_data = copy.deepcopy(state.scene)

        try:
            staged_edges = self._stage_edges(scene_data)
        except KeyError as exc:
            self.on_status(
                "Could not switch to state '%s': missing socket %s" % (state.name, exc)
            )
            return False

        # Node.deserialize swallows its own internal errors, but subclasses
        # (e.g. ShaderNode, node/shader_node_base.py) can still raise past
        # that guard on malformed node data. Snapshot the live graph first so
        # a mid-loop failure here rolls back instead of leaving the scene
        # half-applied -- some nodes on the new state's values, edges still
        # on the old state's.
        rollback = self.scene.serialize()
        try:
            self._apply_parameters(scene_data)
            self._rewire(staged_edges)
        except Exception as exc:
            # restore_window_size=False: this is a same-state restore, not a
            # real transition -- it must not trigger reload_program().
            self.scene.deserialize(rollback, {}, True, restore_window_size=False)
            self.on_status("Could not switch to state '%s': %s" % (state.name, exc))
            return False

        self.current_index = index
        self._evaluate_once()
        return True

    def next(self) -> bool:
        return self.goTo(self.current_index + 1)

    def prev(self) -> bool:
        if self.current_index <= 0:
            return False
        return self.goTo(self.current_index - 1)

    # -- internals --------------------------------------------------------

    def _socket_index(self) -> dict:
        index = {}
        for node in self.scene.nodes:
            for socket in node.inputs + node.outputs:
                index[socket.id] = socket
        return index

    def _stage_edges(self, scene_data: dict) -> list:
        """Resolve every edge to real sockets before touching the scene.

        Raises KeyError if any endpoint is missing -- which is why a failed
        transition cannot half-apply.
        """
        sockets = self._socket_index()
        staged = []
        for edge_data in scene_data.get("edges", []):
            staged.append(
                (
                    sockets[edge_data["start"]],
                    sockets[edge_data["end"]],
                    edge_data.get("edge_type", 2),
                )
            )
        return staged

    def _apply_parameters(self, scene_data: dict) -> None:
        by_id = {node.id: node for node in self.scene.nodes}
        for node_data in scene_data.get("nodes", []):
            node = by_id.get(node_data["id"])
            if node is None:
                continue
            # restore_window_size=False: otherwise changeWindowSize fires
            # reload_program() and recompiles the shader mid-set.
            node.deserialize(node_data, {}, True, restore_window_size=False)

    def _rewire(self, staged_edges: list) -> None:
        for edge in list(self.scene.edges):
            edge.remove()

        for start_socket, end_socket, edge_type in staged_edges:
            Edge(self.scene, start_socket, end_socket, edge_type)

    def _evaluate_once(self) -> None:
        """One render pull after the graph has settled.

        Edge *removal* fires onInputChanged per socket
        (nodeeditor/node_edge.py:300-303, inside Edge.remove()), so
        evaluating during the rewire would cascade. Doing it once at the end
        avoids that.
        """
        self.on_evaluate()
