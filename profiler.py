"""Per-node frame profiler: where the time goes, CPU and GPU separately.

Off by default and costs nothing when off -- nothing is wrapped until
`enable()` runs, so a normal launch is byte-for-byte the code that shipped.
Turn it on with `--profile` (see main.py).

Three questions it answers, which the render loop otherwise hides:

  1. Is a frame CPU-bound or GPU-bound? paintGL's wall time and the sum of
     the GPU timer queries are reported side by side.
  2. Which node costs what, on each side? Every registered program's
     render() is timed individually.
  3. Is any node rendering more than once per frame? The `already_called`
     cache in ShaderNode.render is what stops a diamond in the graph from
     re-rendering a shared branch; a calls/frame above 1.0 means it is
     leaking, which is exactly the shape of "it lags when I have many nodes".

GPU timing uses GL_TIME_ELAPSED queries. Two consequences worth knowing
when reading the output:

  - Results are harvested two frames late. Reading a query the frame it was
    issued blocks until the GPU drains, which is the very stall we are
    hunting -- it would make the profiler the bottleneck it reports.
  - GL_TIME_ELAPSED cannot nest. Only the outermost render() in a call
     chain gets a query; a program that renders another program inside
     itself (Screen calls Mapping) absorbs the inner one's GPU time and is
     marked with a '+' in the report. CPU time is always exact.
"""

import time
from collections import defaultdict

_ns = time.perf_counter_ns

# Two frames of slack before a query result is read (see module docstring).
QUERY_LATENCY_FRAMES = 2

# The uniform-binding path is aggregated under this name rather than
# attributed per node: it is one shared code path (ProgramsUniforms.
# bindUniformToProgram, and the eval() inside it), and the question is
# whether it matters at all, not which node pays for it.
UNIFORM_BUCKET = "(uniform binding)"


class _Bucket:
    __slots__ = ("calls", "cpu_ns", "gpu_ns", "nested", "instances", "max_ns")

    def __init__(self):
        self.calls = 0
        self.cpu_ns = 0
        self.gpu_ns = 0
        # Worst single call in the window. An average hides the one call in a
        # hundred that takes 30 ms, which is exactly the shape of a stutter:
        # the totals stay small while the frame it lands in blows its budget.
        self.max_ns = 0
        # True once this program has run inside another program's render, so
        # the report can flag that its GPU column is folded into its caller.
        self.nested = False
        # Identities of the program objects seen under this label. Buckets are
        # keyed by class name, so three AddAndDiffuse nodes in the graph give
        # three calls per frame with nothing wrong. Only calls in excess of
        # the instance count mean a node is genuinely rendering twice.
        self.instances = set()


class _Span:
    """One timed render(). Holds the GL query, if it got one."""

    __slots__ = ("prof", "label", "t0", "query")

    def __init__(self, prof, label, instance_id=None):
        self.prof = prof
        self.label = label
        self.t0 = 0
        self.query = None
        if instance_id is not None:
            prof.buckets[label].instances.add(instance_id)

    def __enter__(self):
        prof = self.prof
        bucket = prof.buckets[self.label]
        bucket.calls += 1

        if prof.depth == 0 and prof.ctx is not None:
            self.query = prof._acquire_query()
            self.query.__enter__()
        elif prof.depth > 0:
            bucket.nested = True

        prof.depth += 1
        self.t0 = _ns()
        return self

    def __exit__(self, *exc):
        elapsed = _ns() - self.t0
        prof = self.prof
        prof.depth -= 1
        prof.buckets[self.label].cpu_ns += elapsed

        if prof.depth == 0:
            # Only outermost spans count toward "time spent inside nodes":
            # a nested span's CPU is already inside its caller's, so summing
            # every bucket would double-count it and make the leftover
            # (graph traversal, Qt, everything else) come out negative.
            prof.top_cpu_ns += elapsed

        if self.query is not None:
            self.query.__exit__(*exc)
            prof.inflight.append((self.label, self.query))

        return False


class _NullSpan:
    """Returned by gui_span when profiling is off, so call sites cost nothing."""

    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


_NULL_SPAN = _NullSpan()


class _CpuSpan:
    """A timed stretch of GUI-thread work, outside any frame.

    Deliberately separate from _Span: this runs between paints, not inside
    one, so it must not touch the nesting depth (which guards the GL queries)
    nor the per-frame CPU accounting.
    """

    __slots__ = ("prof", "label", "t0")

    def __init__(self, prof, label):
        self.prof = prof
        self.label = label
        self.t0 = 0

    def __enter__(self):
        self.t0 = _ns()
        return self

    def __exit__(self, *exc):
        elapsed = _ns() - self.t0
        bucket = self.prof.gui_buckets[self.label]
        bucket.calls += 1
        bucket.cpu_ns += elapsed
        if elapsed > bucket.max_ns:
            bucket.max_ns = elapsed
        return False


class FrameProfiler:
    def __init__(self):
        self.enabled = False
        self.ctx = None
        self.depth = 0

        self.buckets = defaultdict(_Bucket)
        # GUI-thread work happening between paints: the node editor repaint,
        # and the slots the worker threads fire back into the GUI thread.
        # Reported per second rather than per frame -- these are not paced by
        # the render loop, and their whole significance is how much of the
        # thread's second they consume before a paint event can be served.
        self.gui_buckets = defaultdict(_Bucket)
        # Every event Qt delivers, keyed by receiver class and event type.
        # Populated only under --profile-events; see make_application.
        self.event_buckets = defaultdict(_Bucket)
        self.inflight = []
        # One list of (label, query) per frame still waiting to be read.
        self._pending = []
        self._pool = []

        self.frames = 0
        self.frame_cpu_ns = 0
        self.top_cpu_ns = 0
        # Wall time between one paintGL returning and the next one starting:
        # vsync wait, the Qt event loop, the other timers' slots, and the
        # threadpool hop that requests the paint. Invisible from inside
        # paintGL, and on a vsync-capped app it is usually where the frame
        # actually goes.
        self.outside_ns = 0
        # Of that, the part spent between the shader timer firing and the
        # paint starting -- the dispatch path (app.requestShaderRepaint).
        self.dispatch_ns = 0
        self.dispatch_samples = 0
        self._dispatch_t0 = 0
        self._frame_t0 = 0
        self._frame_end_ns = 0
        self._window_t0 = 0
        # Wall time of each frame period in the window. An average hides a
        # loop that alternates between fast and slow frames, which is exactly
        # what a viewer perceives as stutter -- the percentiles below show it.
        self.frame_periods_ms = []

        self.report_every = 120
        self.sink = print
        # Printed in every report header. Without it two runs that differ only
        # by a launch flag produce byte-identical output, and an A/B becomes
        # unreadable the moment the reports are pasted somewhere.
        self.context = ""

    # -- query pool -------------------------------------------------------

    def _acquire_query(self):
        if self._pool:
            return self._pool.pop()
        return self.ctx.query(time=True)

    def _harvest(self):
        """Read back results issued QUERY_LATENCY_FRAMES frames ago."""
        while len(self._pending) > QUERY_LATENCY_FRAMES:
            for label, query in self._pending.pop(0):
                try:
                    self.buckets[label].gpu_ns += query.elapsed
                except Exception:
                    # A lost context or a released query must not take the
                    # app down -- profiling is never worth a crash.
                    pass
                self._pool.append(query)

    # -- frame boundaries -------------------------------------------------

    def mark_dispatch(self):
        """The shader timer just fired and asked for a repaint."""
        if self.enabled and self._dispatch_t0 == 0:
            # First request since the last paint wins: update() coalesces, so
            # a second request before the paint lands would otherwise reset
            # the clock and hide the queueing we are trying to measure.
            self._dispatch_t0 = _ns()

    def begin_frame(self):
        if not self.enabled:
            return

        # Stamp the clock and close the dispatch window FIRST. _harvest()
        # reads GL query results, which blocks until the GPU has caught up --
        # doing it before this point charged that blocking wait to
        # "attente demande -> paint", making the profiler's own readback look
        # like Qt being slow to deliver the frame.
        now = _ns()

        if self._window_t0 == 0:
            self._window_t0 = now

        if self._frame_end_ns:
            self.outside_ns += now - self._frame_end_ns

        if self._dispatch_t0:
            self.dispatch_ns += now - self._dispatch_t0
            self.dispatch_samples += 1
            self._dispatch_t0 = 0

        with self.gui_span("profiler: lecture des queries GPU"):
            self._harvest()

        self.inflight = []
        # Any span left open by an exception would corrupt the nesting
        # guard for every later frame; the frame boundary is the safe
        # place to reset it.
        self.depth = 0
        self._frame_t0 = _ns()

    def end_frame(self):
        if not self.enabled:
            return
        previous_end = self._frame_end_ns
        self._frame_end_ns = _ns()
        self.frame_cpu_ns += self._frame_end_ns - self._frame_t0

        if previous_end:
            self.frame_periods_ms.append((self._frame_end_ns - previous_end) / 1e6)
        self._pending.append(self.inflight)
        self.inflight = []
        self.frames += 1

        if self.frames >= self.report_every:
            self.sink(self.report())
            self.reset()

    def span(self, label, instance_id=None):
        return _Span(self, label, instance_id)

    def gui_span(self, label):
        if not self.enabled:
            return _NULL_SPAN
        return _CpuSpan(self, label)

    def reset(self):
        self.buckets = defaultdict(_Bucket)
        self.gui_buckets = defaultdict(_Bucket)
        self.event_buckets = defaultdict(_Bucket)
        self.frames = 0
        self.frame_cpu_ns = 0
        self.top_cpu_ns = 0
        self.outside_ns = 0
        self.dispatch_ns = 0
        self.dispatch_samples = 0
        self.frame_periods_ms = []
        # Dropped deliberately: the first period of a new window would
        # otherwise start at the previous window's last frame and swallow the
        # cost of printing the report, which on a Windows console is tens of
        # milliseconds.
        self._frame_end_ns = 0
        self._window_t0 = _ns()

    # -- reporting --------------------------------------------------------

    def report(self):
        n = max(self.frames, 1)
        wall_s = (_ns() - self._window_t0) / 1e9
        fps = self.frames / wall_s if wall_s > 0 else 0.0

        cpu_ms = self.frame_cpu_ns / n / 1e6
        rows = [
            (label, b) for label, b in self.buckets.items() if label != UNIFORM_BUCKET
        ]
        gpu_ms = sum(b.gpu_ns for _, b in rows) / n / 1e6
        node_cpu_ms = self.top_cpu_ns / n / 1e6

        uniform = self.buckets.get(UNIFORM_BUCKET)
        uniform_ms = uniform.cpu_ns / n / 1e6 if uniform else 0.0
        uniform_calls = uniform.calls / n if uniform else 0.0

        budget = 1000.0 / 60.0
        frame_ms = 1000.0 / fps if fps > 0 else 0.0
        outside_ms = self.outside_ns / n / 1e6
        dispatch_ms = (
            self.dispatch_ns / self.dispatch_samples / 1e6
            if self.dispatch_samples
            else 0.0
        )

        if gpu_ms > budget:
            verdict = "GPU sature -- alleger les noeuds"
        elif cpu_ms > budget:
            verdict = "CPU sature dans paintGL"
        else:
            verdict = "ni le CPU ni le GPU ne saturent -- le temps part hors paintGL"

        out = []
        out.append("")
        out.append("=" * 74)
        out.append(
            "PataNode profile  |  %d frames  |  %.1f fps reels  |  budget = %.2f ms"
            % (self.frames, fps, budget)
        )
        if self.context:
            out.append("  config  %s" % self.context)
        out.append("  frame reelle      %7.2f ms" % frame_ms)

        periods = sorted(self.frame_periods_ms)
        if periods:
            def pct(p):
                return periods[min(len(periods) - 1, int(len(periods) * p))]

            # A steady loop has p50 and p99 within a millisecond of each other.
            # A gap between them is the stutter, and its size says whether it
            # is a slow drift or a handful of long frames.
            spikes = sum(1 for v in periods if v > 2.0 * pct(0.50))
            out.append(
                "    p50 %6.2f   p95 %6.2f   p99 %6.2f   max %7.2f ms"
                % (pct(0.50), pct(0.95), pct(0.99), periods[-1])
            )
            out.append(
                "    %d frame(s) sur %d ont dure plus du double de la mediane"
                % (spikes, len(periods))
            )
        out.append(
            "    dans paintGL    %7.2f ms  cpu   (gpu %.2f ms, recouvrable)"
            % (cpu_ms, gpu_ms)
        )
        out.append(
            "    hors paintGL    %7.2f ms  (vsync, event loop, autres timers)"
            % outside_ms
        )
        out.append(
            "      dont attente demande -> paint : %.2f ms  (%d mesures)"
            % (dispatch_ms, self.dispatch_samples)
        )
        out.append("  -> %s" % verdict)
        out.append("-" * 74)
        out.append(
            "%-26s %5s %7s %9s %9s %6s"
            % ("noeud", "inst", "appels", "cpu ms", "gpu ms", "part")
        )
        out.append("-" * 74)

        rows.sort(key=lambda kv: (kv[1].gpu_ns, kv[1].cpu_ns), reverse=True)
        total_gpu_ns = sum(b.gpu_ns for _, b in rows) or 1

        for label, b in rows:
            out.append(
                "%-26s %5d %7.2f %9.3f %9.3f %5.1f%%%s"
                % (
                    label[:26],
                    len(b.instances),
                    b.calls / n,
                    b.cpu_ns / n / 1e6,
                    b.gpu_ns / n / 1e6,
                    100.0 * b.gpu_ns / total_gpu_ns,
                    " +" if b.nested else "",
                )
            )

        out.append("-" * 74)
        out.append(
            "  liaison des uniformes  %.3f ms/frame  (%.0f appels/frame)"
            % (uniform_ms, uniform_calls)
        )
        out.append(
            "  CPU hors noeuds        %.3f ms/frame  (traversee du graphe, Qt, mapping)"
            % (cpu_ms - node_cpu_ms)
        )

        # An instance rendering once per frame is correct, however many
        # instances there are; only calls beyond the instance count mean the
        # already_called cache let a shared branch re-render.
        reeval = [
            (label, b.calls / n, len(b.instances))
            for label, b in rows
            if b.instances and b.calls / n > len(b.instances) * 1.05
        ]
        if reeval:
            out.append("")
            out.append("  /!\\ le cache already_called ne tient pas :")
            for label, calls, inst in reeval:
                out.append(
                    "      %s : %.2f appels pour %d instance(s)" % (label, calls, inst)
                )

        out.append("  '+' = appele par un autre programme : son gpu ms va a l'appelant")

        if self.gui_buckets and wall_s > 0:
            out.append("-" * 74)
            out.append("  hors paintGL, thread GUI (part d'une seconde reelle) :")
            out.append(
                "  %-34s %7s %8s %7s %5s %8s"
                % ("span", "appels/s", "ms/appel", "ms/s", "part", "pire ms")
            )
            gui_rows = sorted(
                self.gui_buckets.items(), key=lambda kv: kv[1].max_ns, reverse=True
            )
            for label, b in gui_rows:
                ms_total = b.cpu_ns / 1e6
                out.append(
                    "  %-34s %7.1f %8.3f %7.1f %4.0f%% %8.2f"
                    % (
                        label[:34],
                        b.calls / wall_s,
                        ms_total / b.calls if b.calls else 0.0,
                        ms_total / wall_s,
                        100.0 * ms_total / (wall_s * 1000.0),
                        b.max_ns / 1e6,
                    )
                )
            out.append(
                "  (drawBackground et node.paint sont contenus dans paintEvent)"
            )

        if self.event_buckets and wall_s > 0:
            out.append("-" * 74)
            out.append("  evenements Qt livres sur le thread GUI, top 12 :")
            out.append(
                "  %-40s %7s %7s %5s %8s"
                % ("receveur / type", "nb/s", "ms/s", "part", "pire ms")
            )
            # Ranked by worst single delivery, not by total: a stutter is one
            # long event, and sorting by total buries it under the many cheap
            # ones that add up to more.
            ev_rows = sorted(
                self.event_buckets.items(), key=lambda kv: kv[1].max_ns, reverse=True
            )
            for label, b in ev_rows[:12]:
                ms_total = b.cpu_ns / 1e6
                out.append(
                    "  %-40s %7.1f %7.1f %4.0f%% %8.2f"
                    % (
                        label[:40],
                        b.calls / wall_s,
                        ms_total / wall_s,
                        100.0 * ms_total / (wall_s * 1000.0),
                        b.max_ns / 1e6,
                    )
                )
            total = sum(b.cpu_ns for _, b in ev_rows) / 1e6
            out.append(
                "  total tous evenements  %.1f ms/s  (%.0f%% du thread GUI, %d cles)"
                % (total / wall_s, 100.0 * total / (wall_s * 1000.0), len(ev_rows))
            )
            out.append(
                "  (imbrique : un paintEvent contient le rendu qu'il declenche)"
            )

        out.append("=" * 74)
        return "\n".join(out)


PROFILER = FrameProfiler()


# -- Qt event accounting --------------------------------------------------
#
# Everything Qt delivers on the GUI thread passes through QApplication.notify.
# Wrapping it is the only way to see the whole thread rather than the handlers
# one thought to instrument -- which is how a 16 ms gap survived a dozen
# targeted measurements. Costs a Python call per event, so it is opt-in.

_EVENT_NAMES = {}


def _event_name(value):
    if not _EVENT_NAMES:
        from PyQt5.QtCore import QEvent

        for name in dir(QEvent):
            attr = getattr(QEvent, name, None)
            if isinstance(attr, int) and name[:1].isupper():
                _EVENT_NAMES.setdefault(int(attr), name)

    return _EVENT_NAMES.get(int(value), "Event%d" % int(value))


def record_event(receiver, event, elapsed_ns):
    """Charge one delivered event to (receiver class, event type)."""
    try:
        key = "%s / %s" % (type(receiver).__name__, _event_name(event.type()))
    except Exception:
        # A receiver whose C++ side is already gone: not worth a crash.
        return

    bucket = PROFILER.event_buckets[key]
    bucket.calls += 1
    bucket.cpu_ns += elapsed_ns
    if elapsed_ns > bucket.max_ns:
        bucket.max_ns = elapsed_ns


def make_application(argv, enabled):
    """Build the QApplication, instrumented if asked for."""
    from PyQt5.QtWidgets import QApplication

    if not enabled:
        return QApplication(argv)

    class ProfilingApplication(QApplication):
        def notify(self, receiver, event):
            t0 = _ns()
            try:
                return QApplication.notify(self, receiver, event)
            finally:
                record_event(receiver, event, _ns() - t0)

    print("[profile] comptabilite des evenements Qt active")
    return ProfilingApplication(argv)


# -- instrumentation ------------------------------------------------------


def _wrap_render(cls, label):
    original = cls.__dict__["render"]

    def render(self, *args, **kwargs):
        with PROFILER.span(label, id(self)):
            return original(self, *args, **kwargs)

    render.__name__ = original.__name__
    render.__doc__ = original.__doc__
    render._patanode_unwrapped = original
    cls.render = render


def _instrument_programs():
    from program.program_conf import SHADER_PROGRAMS

    seen = set()
    for cls in SHADER_PROGRAMS.values():
        if cls in seen or "render" not in cls.__dict__:
            continue
        if getattr(cls.__dict__["render"], "_patanode_unwrapped", None) is not None:
            continue
        seen.add(cls)
        _wrap_render(cls, cls.__name__)


def _instrument_uniforms():
    from program.program_base import ProgramsUniforms

    original = ProgramsUniforms.bindUniformToProgram
    if getattr(original, "_patanode_unwrapped", None) is not None:
        return

    def bindUniformToProgram(self, *args, **kwargs):
        bucket = PROFILER.buckets[UNIFORM_BUCKET]
        bucket.calls += 1
        t0 = _ns()
        try:
            return original(self, *args, **kwargs)
        finally:
            bucket.cpu_ns += _ns() - t0

    bindUniformToProgram._patanode_unwrapped = original
    ProgramsUniforms.bindUniformToProgram = bindUniformToProgram


def _wrap_gui(cls, method_name, label):
    """Time a Qt paint method. Works on inherited methods too.

    QDMGraphicsView does not define paintEvent -- it inherits QGraphicsView's --
    so the lookup has to go through the MRO rather than __dict__, and the
    wrapper is installed on the subclass so only this app's views are timed.
    """
    original = getattr(cls, method_name)

    if getattr(original, "_patanode_unwrapped", None) is not None:
        return

    def wrapper(self, *args, **kwargs):
        with PROFILER.gui_span(label):
            return original(self, *args, **kwargs)

    wrapper._patanode_unwrapped = original
    setattr(cls, method_name, wrapper)


def _instrument_gui():
    from nodeeditor.node_graphics_node import QDMGraphicsNode
    from nodeeditor.node_graphics_scene import QDMGraphicsScene
    from nodeeditor.node_graphics_view import QDMGraphicsView

    _wrap_gui(QDMGraphicsView, "paintEvent", "node editor: paintEvent")
    _wrap_gui(QDMGraphicsScene, "drawBackground", "  node editor: grille")
    _wrap_gui(QDMGraphicsNode, "paint", "  node editor: paint d'un noeud")


def enable(ctx, report_every=120, sink=print, context=""):
    """Start profiling. Call once, after the GL context exists."""
    if PROFILER.enabled:
        return PROFILER

    PROFILER.ctx = ctx
    PROFILER.report_every = report_every
    PROFILER.sink = sink
    PROFILER.context = context
    _instrument_programs()
    _instrument_uniforms()
    _instrument_gui()
    PROFILER.enabled = True
    PROFILER.reset()

    print(
        "[profile] actif -- rapport toutes les %d frames. "
        "Ouvre la fenetre shader pour que le rendu demarre." % report_every
    )
    return PROFILER
