"""Drives a live session against a scene.

Union model: every node any state uses is instantiated once at load, so all
GLSL compiles up front. A state then only rewires edges and applies
parameter values -- no construction, no compilation, no hitch mid-set.
"""

import copy

from nodeeditor.node_edge import Edge
from session.trigger import evaluate_trigger, make_entry_snapshot
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

        self.is_playing = False
        self._entry = {}
        self._last_features = {}
        self._now = 0.0
        # Index of the state we've already warned about having a malformed
        # trigger, so tick() (60 Hz) reports it once instead of spamming
        # on_status every frame.
        self._bad_trigger_index = None

    def load(self, session, known_opcodes: set, known_features: set) -> list:
        """Instantiate the union and return every problem found.

        This is the slow step: it compiles every shader the session uses.

        A session with no states has an empty union. Scene.deserialize
        removes every node absent from the incoming data (its normal
        reuse-and-remove semantics), so feeding it {"nodes": [], "edges":
        []} would silently delete the whole open graph. A session with no
        states yet has nothing to instantiate, so leave the scene alone.
        """
        self.session = session
        self.current_index = -1
        self.findings = validate_session(session, known_opcodes, known_features)

        if not session.states:
            return self.findings

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
            try:
                self.scene.deserialize(rollback, {}, True, restore_window_size=False)
            except Exception as rollback_exc:
                self.on_status(
                    "Could not switch to state '%s': %s (rollback also failed: %s)"
                    % (state.name, exc, rollback_exc)
                )
                return False
            self.on_status("Could not switch to state '%s': %s" % (state.name, exc))
            return False

        self.current_index = index
        # Snapshot lazily on the next tick, not here: at goTo time
        # self._last_features may be stale (e.g. {} from __init__, before
        # any tick has run) or simply belong to a different moment than
        # when the audience actually starts hearing this state. Anchoring
        # against a stale/zero baseline lets a monotonic counter's delta
        # blow past the threshold on the very next tick -- an instant,
        # unwanted auto-advance right after load. None means "not yet
        # anchored"; tick() takes the real snapshot from live features.
        self._entry = None
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
        # silent=True: Edge.remove() otherwise notifies both endpoint nodes
        # per removed edge (onEdgeConnectionChanged + onInputChanged on the
        # input side -- nodeeditor/node_edge.py:290-303), and
        # ShaderNode.onInputChanged calls self.eval() (node/shader_node_base.py).
        # Without silencing this, every removed edge triggers a full
        # upstream render pull while the graph is half torn down -- exactly
        # the mid-transition hitching the union model exists to avoid.
        for edge in list(self.scene.edges):
            edge.remove(silent=True)

        for start_socket, end_socket, edge_type in staged_edges:
            Edge(self.scene, start_socket, end_socket, edge_type)

    def _evaluate_once(self) -> None:
        """One render pull after the graph has settled.

        Edge *removal* fires onInputChanged per socket
        (nodeeditor/node_edge.py:290-303, inside Edge.remove()), which for a
        ShaderNode triggers a real evaluation -- so evaluating during the
        rewire would cascade. _rewire silences that (silent=True) and this
        is the single evaluation that replaces it, done once at the end.
        """
        self.on_evaluate()

    # -- playback -----------------------------------------------------------

    def play(self) -> None:
        self.is_playing = True

    def pause(self) -> None:
        self.is_playing = False

    def tick(self, features: dict, now: float) -> None:
        """Called from the audio timer. Advances if the trigger fires."""
        self._last_features = features
        self._now = now

        if not self.is_playing or self.session is None:
            return
        if not (0 <= self.current_index < len(self.session.states)):
            return

        trigger = self.session.states[self.current_index].trigger

        if self._entry is None:
            # First tick since goTo landed on this state: anchor the
            # baseline against features observed right now, not whatever
            # was stale (or absent) at goTo time. Don't evaluate against
            # it in the same tick -- that would let a single tick both
            # anchor and immediately fire off a coincidental delta.
            try:
                self._entry = make_entry_snapshot(trigger, features, now)
            except KeyError:
                self._entry = {}
                self._report_bad_trigger()
            return

        # A malformed trigger (e.g. a threshold trigger missing "hold") must
        # degrade to "never advances", not escape into the 60 Hz Qt audio
        # slot (SessionPlayer.tick is called from app.py:122's
        # on_audio_job_finished) mid-performance. validate_session rejects
        # this shape at load time; this is the last-ditch guard for a
        # session file that was hand-edited after loading, or a future
        # trigger shape the validator doesn't know about yet.
        try:
            result = evaluate_trigger(trigger, features, self._entry, now)
        except KeyError:
            self._report_bad_trigger()
            return

        self._entry = result.entry

        if result.should_advance:
            self.next()

    def _report_bad_trigger(self) -> None:
        if self._bad_trigger_index == self.current_index:
            return  # already warned about this state; don't spam at 60 Hz
        self._bad_trigger_index = self.current_index
        self.on_status(
            "State %d has a malformed trigger and will never auto-advance"
            % self.current_index
        )
