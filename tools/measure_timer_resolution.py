"""How fast can a Qt timer actually fire on this machine?

The render loop re-arms itself with a zero-delay QTimer, and the profiler
measures 16-21 ms between arming it and it firing. A zero-delay timer should
fire on the next pass of the event loop, well under a millisecond. If it
cannot, nothing else about the loop matters: the frame rate is capped by the
timer, not by the rendering.

Windows schedules timers against a global tick whose default period is
15.625 ms. A process can ask for a finer one with timeBeginPeriod, and many
media applications do. This script measures the firing rate before and after
that request, on this machine, with nothing else running.

    .venv/Scripts/python.exe tools/measure_timer_resolution.py

No Qt widgets, no GL, no PataNode -- just the timer.
"""

import sys
import time

from PyQt5.QtCore import QCoreApplication, Qt, QTimer

SHOTS = 400


def measure(app, label):
    """Fire a zero-delay single-shot timer SHOTS times, re-arming each time."""
    stamps = []
    timer = QTimer()
    timer.setSingleShot(True)
    # Same type the render loop uses. Qt documents this as "as accurate as the
    # platform allows", which is precisely what is in question here.
    timer.setTimerType(Qt.PreciseTimer)

    def tick():
        stamps.append(time.perf_counter_ns())
        if len(stamps) < SHOTS:
            timer.start(0)
        else:
            app.quit()

    timer.timeout.connect(tick)
    timer.start(0)
    app.exec_()

    gaps = sorted(
        (stamps[i + 1] - stamps[i]) / 1e6 for i in range(len(stamps) - 1)
    )
    median = gaps[len(gaps) // 2]

    print("%s" % label)
    print(
        "    median %7.3f ms    min %7.3f    max %7.3f    -> plafond %.0f fps"
        % (median, gaps[0], gaps[-1], 1000.0 / median if median else 0.0)
    )
    return median


def main():
    app = QCoreApplication(sys.argv)

    print()
    print("QTimer(0), %d tirs consecutifs" % SHOTS)
    print("-" * 68)

    before = measure(app, "  resolution par defaut")

    if not sys.platform.startswith("win"):
        print("\n  (timeBeginPeriod est propre a Windows -- rien de plus a tester)")
        return

    import ctypes

    # 1 ms is what DirectX games and media players request. It is a process
    # -wide request that Windows honours globally while at least one process
    # holds it; timeEndPeriod below gives it back.
    ctypes.windll.winmm.timeBeginPeriod(1)
    try:
        after = measure(app, "  apres timeBeginPeriod(1)")
    finally:
        ctypes.windll.winmm.timeEndPeriod(1)

    print("-" * 68)

    if before > 5.0 and after < before / 2:
        print("  => L'horloge systeme bridait bien les timers.")
        print(
            "     Le plafond passe de %.0f a %.0f fps, sans toucher au rendu."
            % (1000.0 / before, 1000.0 / after)
        )
    elif before < 5.0:
        print("  => Les timers tirent deja vite. L'horloge n'est pas en cause,")
        print("     et les 16-21 ms mesurees dans PataNode viennent d'ailleurs.")
    else:
        print("  => timeBeginPeriod ne change rien ici. Piste fermee.")
    print()


if __name__ == "__main__":
    main()
