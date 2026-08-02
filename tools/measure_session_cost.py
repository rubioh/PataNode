"""Measure the automatable half of Task 10.

Two questions the design rests on:

  1. Is the non-GL cost of a transition negligible?  (union build, parameter
     application, edge rewiring)  -- fully measurable headlessly.
  2. What does session load cost, given it compiles every shader up front?
     -- needs a real GL context; attempted via a standalone moderngl context,
     skipped honestly if unavailable.

Run from the repo root:
    QT_QPA_PLATFORM=offscreen .venv/bin/python \
        .superpowers/sdd/2026-08-02-live-session/measure_session_cost.py
"""

import copy
import time

from PyQt5.QtWidgets import QApplication  # noqa: E402

import program.program_conf  # noqa: F401  breaks the import cycle; must be first


def build_state(n_nodes, wire=True):
    """A scene dict with n_nodes plain nodes, optionally chained together."""
    nodes = []
    for i in range(n_nodes):
        nodes.append(
            {
                "id": 1000 + i,
                "title": "N%d" % i,
                "pos_x": i * 50,
                "pos_y": 0,
                "op_code": 100,
                "inputs": [
                    {
                        "id": 2000 + i,
                        "index": 0,
                        "multi_edges": False,
                        "position": 2,
                        "socket_type": 1,
                    }
                ],
                "outputs": [
                    {
                        "id": 3000 + i,
                        "index": 0,
                        "multi_edges": True,
                        "position": 5,
                        "socket_type": 1,
                    }
                ],
                "content": {},
            }
        )

    edges = []
    if wire:
        for i in range(n_nodes - 1):
            edges.append(
                {
                    "id": 4000 + i,
                    "start": 3000 + i,
                    "end": 2000 + i + 1,
                    "edge_type": 2,
                }
            )

    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": nodes,
        "edges": edges,
    }


def measure_non_gl(n_nodes=40, n_states=30):
    from nodeeditor.node_node import Node
    from nodeeditor.node_scene import Scene
    from session.model import LiveSession, SessionState
    from session.player import SessionPlayer

    states = []
    for s in range(n_states):
        # every state wires a growing prefix of the graph
        scene = build_state(n_nodes, wire=False)
        full = build_state(n_nodes, wire=True)
        keep = max(1, int(len(full["edges"]) * (s + 1) / n_states))
        scene["edges"] = copy.deepcopy(full["edges"][:keep])
        states.append(SessionState("state %d" % s, {"type": "manual"}, scene))

    session = LiveSession(name="bench", states=states)

    scene = Scene()
    scene.setNodeClassSelector(lambda data: Node)
    player = SessionPlayer(scene)

    t0 = time.perf_counter()
    player.load(session, {100}, set())
    load_ms = (time.perf_counter() - t0) * 1000

    # warm one transition, then time the rest
    player.goTo(0)
    timings = []
    for i in range(1, n_states):
        t0 = time.perf_counter()
        ok = player.goTo(i)
        timings.append((time.perf_counter() - t0) * 1000)
        assert ok, "goTo(%d) failed" % i

    timings.sort()
    print("--- non-GL cost (%d nodes, %d states) ---" % (n_nodes, n_states))
    print("  union load (no GL)      : %7.1f ms" % load_ms)
    print("  transition median       : %7.2f ms" % timings[len(timings) // 2])
    print("  transition worst        : %7.2f ms" % timings[-1])
    print("  frame budget @60fps     :   16.67 ms")
    verdict = "WITHIN" if timings[-1] < 16.67 else "OVER"
    print("  worst transition is %s one frame budget" % verdict)


def measure_gl_compile():
    print()
    print("--- GL shader compile cost ---")
    try:
        import moderngl
    except ImportError:
        print("  moderngl not importable - SKIPPED")
        return

    try:
        ctx = moderngl.create_standalone_context()
    except Exception as exc:
        print("  no standalone GL context available here: %s" % exc)
        print("  SKIPPED - session load cost must be measured in the real app")
        return

    from os.path import dirname, join

    import program.program_conf as pc

    vert = open(pc.SQUARE_VERT_PATH).read()
    frag_path = join(dirname(pc.__file__), "colors", "bloom", "bloom.glsl")
    try:
        frag = open(frag_path).read()
    except OSError:
        print("  sample shader not found at %s - SKIPPED" % frag_path)
        return

    timings = []
    for _ in range(10):
        t0 = time.perf_counter()
        prog = ctx.program(vertex_shader=vert, fragment_shader=frag)
        timings.append((time.perf_counter() - t0) * 1000)
        prog.release()

    timings.sort()
    median = timings[len(timings) // 2]
    print("  single program compile  : %7.2f ms (median of 10)" % median)
    for n in (15, 40):
        print("  extrapolated %2d-node load: %7.1f ms" % (n, median * n))
    print("  NOTE: real nodes compile more than one program each, so treat")
    print("        these as a floor, not an estimate.")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    measure_non_gl()
    measure_gl_compile()
