"""Depth capture in a child process, so its GIL cost cannot stall rendering.

The Orbbec filter chain holds the GIL for about 68% of the 14.5 ms it spends
on each frame. At 31 fps that is roughly 306 ms a second during which no other
Python in the process can run -- including the render loop. Measured against
the real camera, in-process capture costs 5 fps and pushes the p99 frame
interval from 15.6 ms to 22.7 ms.

A child process has its own GIL, so the filters stop competing with rendering
and all five can be kept rather than traded away for frame rate.
"""

from multiprocessing import shared_memory

import numpy as np

# Frame slots start here. One page, far more than the header needs, so the
# slots land on a page boundary and the layout stays readable in a hex dump.
HEADER_SIZE = 4096

# Header fields, as indices into a uint32 view of the first bytes.
_SEQ = 0
_SLOT = 1
_WIDTH = 2
_HEIGHT = 3

# uint32 seq wraps after 2**32 frames, which is over four years at 31 fps.
_SEQ_MODULO = 1 << 32

# A read retries only if the writer landed mid-copy. At 31 fps against a copy
# measured in microseconds that is vanishingly rare, so a low cap is honest:
# if it ever exhausts, something is wrong and returning None is correct.
_READ_ATTEMPTS = 4


class FrameRing:
    """Double-buffered uint16 frames in shared memory, newest-wins.

    One writer (the child) and one reader (the render process), coordinated by
    a sequence counter rather than a lock: the writer fills the slot the reader
    is not looking at, publishes it, then bumps `seq`. The reader samples `seq`,
    copies, and re-samples; a change means the writer overtook it mid-copy and
    the attempt is discarded.

    Deliberately not a Queue. A queue would buffer stale depth frames whenever
    the reader fell behind, and for live visuals the newest frame is the only
    one worth having.
    """

    def __init__(self, shm, width, height):
        self._shm = shm
        self.name = shm.name
        self.width = width
        self.height = height

        frame_bytes = width * height * 2
        self._header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf)
        self._slots = [
            np.ndarray(
                (height, width),
                dtype=np.uint16,
                buffer=shm.buf,
                offset=HEADER_SIZE + index * frame_bytes,
            )
            for index in (0, 1)
        ]

    @classmethod
    def create(cls, width, height):
        size = HEADER_SIZE + 2 * width * height * 2
        shm = shared_memory.SharedMemory(create=True, size=size)
        ring = cls(shm, width, height)
        ring._header[_SEQ] = 0
        ring._header[_SLOT] = 0
        ring._header[_WIDTH] = width
        ring._header[_HEIGHT] = height
        return ring

    @classmethod
    def attach(cls, name):
        shm = shared_memory.SharedMemory(name=name)

        # Deliberately left registered with the resource_tracker. On the
        # normal path the creator's unlink() clears this block's entry, so
        # attaching here warns about nothing. On the abnormal path -- the
        # creator dies before it unlinks -- the tracker's "leaked shared_memory
        # objects" warning is the honest signal that a block was orphaned, not
        # noise to be suppressed.

        header = np.ndarray((4,), dtype=np.uint32, buffer=shm.buf)
        return cls(shm, int(header[_WIDTH]), int(header[_HEIGHT]))

    def _seq(self):
        return int(self._header[_SEQ])

    def write(self, frame):
        """Publish a frame. Only the child calls this."""
        slot = 1 - int(self._header[_SLOT])
        self._slots[slot][:] = frame
        self._header[_SLOT] = slot
        self._header[_SEQ] = (self._seq() + 1) % _SEQ_MODULO

    def read(self, last_seq):
        """The newest frame if it is not `last_seq`, else (None, last_seq)."""
        for _ in range(_READ_ATTEMPTS):
            seq = self._seq()

            if seq == last_seq:
                return None, last_seq

            slot = int(self._header[_SLOT])
            # Copy: the writer will overwrite this slot, and the caller holds
            # the array until it reaches the GPU.
            frame = self._slots[slot].copy()

            if self._seq() == seq:
                return frame, seq

        return None, last_seq

    def close(self):
        """Detach. Both sides call this; only the creator unlinks."""
        self._header = None
        self._slots = []
        self._shm.close()

    def unlink(self):
        """Destroy the block. Only the creating process calls this."""
        self._shm.unlink()
