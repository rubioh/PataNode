"""The shared-memory transport between the depth child and the render process."""

import numpy as np
import pytest

from depth.depth_process import HEADER_SIZE, FrameRing


@pytest.fixture
def ring():
    r = FrameRing.create(4, 3)
    yield r
    r.close()
    r.unlink()


def make_frame(value, width=4, height=3):
    return np.full((height, width), value, dtype=np.uint16)


def test_a_reader_sees_nothing_before_the_first_write(ring):
    reader = FrameRing.attach(ring.name)
    try:
        frame, seq = reader.read(0)
        assert frame is None
        assert seq == 0
    finally:
        reader.close()


def test_a_written_frame_comes_back_intact(ring):
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(1234))
        frame, seq = reader.read(0)

        assert seq != 0
        assert frame.shape == (3, 4)
        assert frame.dtype == np.uint16
        assert (frame == 1234).all()
    finally:
        reader.close()


def test_reading_twice_without_a_write_returns_nothing(ring):
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(7))
        _, seq = reader.read(0)
        frame, seq2 = reader.read(seq)

        assert frame is None
        assert seq2 == seq
    finally:
        reader.close()


def test_a_stalled_reader_gets_the_newest_frame_not_the_oldest(ring):
    # Latest-frame-wins is the whole reason this is shared memory rather than
    # a Queue: a backlog of stale depth frames is worse than a dropped one.
    reader = FrameRing.attach(ring.name)
    try:
        for value in (1, 2, 3, 4, 5):
            ring.write(make_frame(value))

        frame, _ = reader.read(0)
        assert (frame == 5).all()
    finally:
        reader.close()


def test_attach_recovers_the_dimensions_from_the_header(ring):
    reader = FrameRing.attach(ring.name)
    try:
        assert reader.width == 4
        assert reader.height == 3
    finally:
        reader.close()


def test_the_returned_frame_is_a_copy_not_a_live_view(ring):
    # The child overwrites slots continuously. A view would mutate under the
    # caller between the read and the texture upload.
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(11))
        frame, _ = reader.read(0)
        ring.write(make_frame(22))
        ring.write(make_frame(33))

        assert (frame == 11).all()
    finally:
        reader.close()


def test_a_torn_read_is_retried(ring, monkeypatch):
    # Simulates the writer landing mid-copy: seq moves between the reader's
    # two samples, so the first attempt must be discarded.
    reader = FrameRing.attach(ring.name)
    try:
        ring.write(make_frame(1))
        seen = {"n": 0}
        real = reader._seq

        def flaky():
            seen["n"] += 1
            # Report a different seq on the confirming sample of attempt 1.
            if seen["n"] == 2:
                return real() + 99
            return real()

        monkeypatch.setattr(reader, "_seq", flaky)
        frame, _ = reader.read(0)

        assert frame is not None
        assert seen["n"] > 2
    finally:
        reader.close()
