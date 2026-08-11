"""Drives a live session against a scene.

Union model: every node any state uses is instantiated once at load, so all
GLSL compiles up front. A state then only rewires edges and applies
parameter values -- no construction, no compilation, no hitch mid-set.
"""

import copy

from nodeeditor.node_edge import Edge
from session.fade import MAX_NESTING, ActiveFade, ResolvedFade, is_blendable
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
        # The eased transition currently in flight, or None for a hard cut.
        # Advanced from tick(); see session/fade.py.
        self._active_fade = None
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
        self._active_fade = None
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

        # Read the outgoing values before _apply_parameters overwrites them
        # with the incoming state's -- these are the "from" side of the fade.
        # Reading live (rather than from the previous state's dict) is what
        # makes a fade work no matter which state you jumped from, and what
        # makes an interrupted fade seamless: the half-blended expression
        # currently on the parameter is what gets eased away from. A no-op
        # when the state has no fade.
        fade_spec = getattr(state, "fade", None)
        fade_sources = self._capture_fade_sources(fade_spec)

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
        # After the rewire, so a failed switch never leaves a fade running
        # against a scene that rolled back.
        self._start_fade(fade_spec, fade_sources)
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

    # -- fades --------------------------------------------------------------

    @staticmethod
    def _read_live_param(node, program, uniform):
        """The expression string a node currently holds for one uniform.

        Returns None for anything that isn't a real ShaderNode carrying that
        uniform -- a fade must degrade to a hard cut, never raise into the
        60 Hz audio slot that drives tick().
        """
        getter = getattr(node, "getGpuAdaptableParameters", None)
        if getter is None:
            return None
        try:
            return getter()[program][uniform]["eval_function"]["value"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _write_live_param(node, program, uniform, value) -> bool:
        """Write an expression straight into the live parameter dict.

        No render pull needed: bindUniformToProgram re-reads and re-evals
        this string every frame (program/program_base.py:706), so writing it
        is the whole of applying a fade step.
        """
        setter = getattr(getattr(node, "program", None), "setAdaptableParameters", None)
        if setter is None:
            return False
        try:
            setter(program, uniform, "eval_function", value)
        except (KeyError, TypeError):
            return False
        return True

    def _capture_fade_sources(self, fade_spec) -> dict:
        """Live "from" values, read before the incoming state is applied."""
        if fade_spec is None or not fade_spec.params:
            return {}

        by_id = {node.id: node for node in self.scene.nodes}
        sources = {}
        for param in fade_spec.params:
            if param.from_value is not None:
                continue  # explicit override; nothing to read
            node = by_id.get(param.node_id)
            if node is None:
                continue
            sources[param.key] = self._read_live_param(
                node, param.program, param.uniform
            )
        return sources

    def _start_fade(self, fade_spec, fade_sources) -> None:
        """Resolve both endpoints and put the parameters at their old values.

        Runs after _apply_parameters, so an unspecified "to" is simply what
        the incoming state just wrote. Writing the a=0 expression here (and
        not waiting for the first tick) means the first rendered frame shows
        the outgoing value rather than flashing the incoming one.
        """
        superseded = self._active_fade
        self._active_fade = None

        if fade_spec is None or not fade_spec.params:
            return

        previous = (
            {entry.key: entry for entry in superseded.entries} if superseded else {}
        )
        by_id = {node.id: node for node in self.scene.nodes}

        entries = []
        for param in fade_spec.params:
            node = by_id.get(param.node_id)
            if node is None:
                continue  # validate_session already reported this

            old = (
                param.from_value
                if param.from_value is not None
                else fade_sources.get(param.key)
            )
            new = (
                param.to_value
                if param.to_value is not None
                else self._read_live_param(node, param.program, param.uniform)
            )

            depth = 0
            interrupted = previous.get(param.key)
            if interrupted is not None:
                # `old` is the interrupted fade's own half-blended
                # expression, which is why resuming from it looks seamless.
                # Each interruption wraps it one level deeper, so past the
                # cap fall back to that fade's clean target instead.
                depth = interrupted.depth + 1
                if depth > MAX_NESTING:
                    old, depth = interrupted.new, 0

            if not (is_blendable(old) and is_blendable(new)) or old == new:
                # Nothing to ease between: _apply_parameters already put the
                # parameter on the incoming value, so this one hard-cuts.
                continue

            entries.append(
                ResolvedFade(
                    param.node_id, param.program, param.uniform, old, new, depth
                )
            )

        if not entries:
            return

        # start=None: anchored on the first tick, not here. self._now is
        # whatever the last audio tick reported, which before any tick is
        # 0.0 -- anchoring against that would make the very first real tick
        # see an elapsed time of "since the epoch" and snap the fade shut.
        # Same lazy-anchor reasoning as self._entry above.
        self._active_fade = ActiveFade(
            entries, fade_spec.duration, fade_spec.curve, None
        )
        self._write_fade(self._active_fade, 0.0)

    def _write_fade(self, fade, a: float) -> None:
        by_id = {node.id: node for node in self.scene.nodes}
        for entry in fade.entries:
            node = by_id.get(entry.node_id)
            if node is None:
                continue
            self._write_live_param(
                node, entry.program, entry.uniform, entry.value_at(a)
            )

    def _advance_fade(self, now: float) -> None:
        fade = self._active_fade
        if fade is None:
            return

        if fade.start is None:
            fade.start = now
            return  # already sitting at a=0 from _start_fade

        if fade.is_done(now):
            self.finishFade()
            return

        self._write_fade(fade, fade.progress(now))

    def finishFade(self) -> None:
        """Snap every fading parameter to its real target string.

        Public because a synthesized blend expression must never reach a
        saved file: capturing or overwriting a state mid-fade serializes the
        live scene, and "(1-0.4)*(x*2)+(0.4)*(.9)" would be baked in as if
        the user had typed it. Same class of bug as commit 7ba3213.
        """
        fade = self._active_fade
        if fade is None:
            return

        self._active_fade = None
        by_id = {node.id: node for node in self.scene.nodes}
        for entry in fade.entries:
            node = by_id.get(entry.node_id)
            if node is None:
                continue
            self._write_live_param(node, entry.program, entry.uniform, entry.new)

    # -- playback -----------------------------------------------------------

    def play(self) -> None:
        self.is_playing = True

    def pause(self) -> None:
        self.is_playing = False

    def tick(self, features: dict, now: float) -> None:
        """Called from the audio timer. Advances if the trigger fires."""
        self._last_features = features
        self._now = now

        # Before the is_playing guard: manual transport works while paused,
        # so a fade started by the Next button must still run to completion.
        self._advance_fade(now)

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
