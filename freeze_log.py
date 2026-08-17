"""Catch render freezes and record what every thread was doing during them.

Off unless PATANODE_FREEZE_LOG is set, and it installs nothing at all in that
case -- no thread, no wrappers, no GC callback. A normal launch runs the
original code.

    PATANODE_FREEZE_LOG=1 python main.py -o saved/scene.pn

Why a sampler rather than timers around suspicious calls: a freeze that is
already understood well enough to bracket does not need finding. This watches
a heartbeat that the render loop updates every frame, and when the heartbeat
goes stale it photographs the Python stack of *every* thread, repeatedly,
until it moves again. Whatever is holding things up is in those stacks --
including work on a worker thread, since anything holding the GIL stops the
render loop just as effectively as work on the GUI thread would.

Two known blind spots, both worth knowing when reading a log:

  - A C call that releases the GIL and blocks (a driver wait, an SDK filter,
    a socket read) shows only the Python frame that called it. That is still
    the answer -- it names the call -- but the time is spent below Python.
  - A C call that does NOT release the GIL freezes the sampler thread too, so
    the stall is measured but may be sampled sparsely. The stall duration is
    taken from the heartbeat, not from the samples, so it stays accurate.

Tunables:
    PATANODE_FREEZE_LOG=1          enable
    PATANODE_FREEZE_MS=50          stall threshold in ms (default 50)
    PATANODE_FREEZE_DIR=Log        where to write (default Log/)
"""

import datetime
import gc
import os
import sys
import threading
import time
import traceback

_state = None


class _Recorder:
    def __init__(self, threshold_ms, path):
        self.threshold_ms = threshold_ms
        self.path = path
        self.heartbeat = time.perf_counter()
        self.main_tid = threading.get_ident()
        self.frame_ms = []
        self.stalls = []
        self.gc_pauses = []
        self._gc_t0 = None
        self._stop = threading.Event()
        self._fh = open(path, "w", buffering=1)

    # ------------------------------------------------------------- plumbing
    def log(self, text):
        self._fh.write(text + "\n")

    def beat(self):
        self.heartbeat = time.perf_counter()

    def gc_callback(self, phase, info):
        if phase == "start":
            self._gc_t0 = time.perf_counter()
        elif self._gc_t0 is not None:
            self.gc_pauses.append(
                ((time.perf_counter() - self._gc_t0) * 1000, info.get("generation"))
            )
            self._gc_t0 = None

    # ------------------------------------------------------------ watchdog
    def run(self):
        while not self._stop.is_set():
            time.sleep(0.004)

            if (time.perf_counter() - self.heartbeat) * 1000 < self.threshold_ms:
                continue

            began = self.heartbeat
            samples = []

            while not self._stop.is_set():
                elapsed = (time.perf_counter() - began) * 1000
                if elapsed < self.threshold_ms:
                    break

                samples.append((elapsed, self._snapshot()))

                if self.heartbeat != began:
                    break
                time.sleep(0.02)

            end = self.heartbeat if self.heartbeat != began else time.perf_counter()
            self._record((end - began) * 1000, samples)

    def _snapshot(self):
        names = {t.ident: t.name for t in threading.enumerate()}
        me = threading.get_ident()
        out = []

        for tid, frame in sys._current_frames().items():
            if tid == me:
                continue
            label = names.get(tid, "?")
            if tid == self.main_tid:
                label = "MAIN/gui"
            out.append((label, "".join(traceback.format_stack(frame))))

        return out

    def _record(self, duration_ms, samples):
        self.stalls.append(duration_ms)
        stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

        self.log("\n" + "=" * 72)
        self.log("STALL %.0f ms at %s" % (duration_ms, stamp))
        self.log("=" * 72)

        for at, snap in samples:
            self.log("\n  --- sampled t+%.0f ms into the stall ---" % at)
            for label, stack in snap:
                self.log("  [%s]" % label)
                for line in stack.rstrip().splitlines():
                    self.log("    " + line)

        self._fh.flush()

    # -------------------------------------------------------------- report
    def report(self):
        self._stop.set()
        warm = sorted(self.frame_ms[20:])
        lines = ["", "=" * 72, "FREEZE LOG SUMMARY", "=" * 72]

        if warm:
            n = len(warm)
            lines.append(
                "frames        : %d   p50 %.2f ms  p99 %.2f ms  max %.2f ms"
                % (n, warm[n // 2], warm[int(n * 0.99)], warm[-1])
            )
            for limit in (50, 100, 250, 500):
                over = sum(1 for m in warm if m > limit)
                if over:
                    lines.append("frames >%dms : %d" % (limit, over))

        if self.stalls:
            s = sorted(self.stalls)
            lines.append(
                "stalls >%dms  : %d   p50 %.0f ms  max %.0f ms"
                % (self.threshold_ms, len(s), s[len(s) // 2], s[-1])
            )
        else:
            lines.append("stalls >%dms  : none" % self.threshold_ms)

        if self.gc_pauses:
            worst = max(self.gc_pauses)
            total = sum(p[0] for p in self.gc_pauses)
            gen2 = [p[0] for p in self.gc_pauses if p[1] == 2]
            lines.append(
                "gc            : %d pauses, %.0f ms total, worst %.0f ms (gen%s)"
                % (len(self.gc_pauses), total, worst[0], worst[1])
            )
            if gen2:
                lines.append("gc gen2       : %d, max %.0f ms" % (len(gen2), max(gen2)))

        lines += ["", "full stacks: %s" % self.path, "=" * 72, ""]
        text = "\n".join(lines)

        self.log(text)
        self._fh.flush()
        sys.stderr.write(text)


def install():
    """Start the watchdog if PATANODE_FREEZE_LOG is set. Otherwise do nothing."""
    global _state

    if not os.environ.get("PATANODE_FREEZE_LOG"):
        return None

    if _state is not None:
        return _state

    threshold = float(os.environ.get("PATANODE_FREEZE_MS", 50))
    directory = os.environ.get("PATANODE_FREEZE_DIR", "Log")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(
        directory,
        "freeze-%s.log" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
    )

    rec = _Recorder(threshold, path)

    # Wrapped here rather than in the widget so that shader_widget.py carries
    # no trace of this: with the variable unset, none of it is reachable.
    from gui.widgets.shader_widget import ShaderWidget

    original = ShaderWidget.drawFrame

    def drawFrame(self):
        t0 = time.perf_counter()
        rec.heartbeat = t0
        try:
            return original(self)
        finally:
            t1 = time.perf_counter()
            rec.heartbeat = t1
            rec.frame_ms.append((t1 - t0) * 1000)

    ShaderWidget.drawFrame = drawFrame

    gc.callbacks.append(rec.gc_callback)
    threading.Thread(target=rec.run, name="freeze-watchdog", daemon=True).start()

    rec.log(
        "PataNode freeze log -- threshold %.0f ms, started %s"
        % (threshold, datetime.datetime.now().isoformat(timespec="seconds"))
    )
    sys.stderr.write(
        "[freeze-log] watching for stalls over %.0f ms -> %s\n" % (threshold, path)
    )

    _state = rec
    return rec


def report():
    """Print and write the summary. Safe to call when not installed."""
    if _state is not None:
        _state.report()
