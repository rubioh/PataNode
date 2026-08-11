"""The .pnlive session document.

A session is an ordered list of states. A state is a normal scene snapshot
(exactly what Scene.serialize produces) plus a name and a trigger, so every
state stays independently loadable as a plain .pn file.

Pure data: no Qt, no GL.
"""

import json
import os

from session.fade import FadeSpec

# Still 1 after the fade block was added, deliberately. `fade` is optional
# and omitted when absent, so old files load unchanged and an older build
# reading a new file simply drops the key. Bumping the version would make
# from_dict below reject every session file already on disk outright.
SESSION_VERSION = 1


class UnknownSessionVersion(Exception):
    """Session file has a version this build cannot read."""


class InvalidSessionFile(Exception):
    """Session file is not valid JSON."""


class SessionState:
    def __init__(self, name: str, trigger: dict, scene: dict, fade=None):
        self.name = name
        self.trigger = trigger
        self.scene = scene
        # How this state eases in when the session arrives at it, or None
        # for the original hard cut. See session/fade.py.
        self.fade = fade

    def to_dict(self) -> dict:
        data = {"name": self.name, "trigger": self.trigger, "scene": self.scene}
        # Omitted entirely when there is no fade, so a session that never
        # used the feature round-trips byte-identically.
        if self.fade is not None:
            data["fade"] = self.fade.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            name=data.get("name", ""),
            trigger=data.get("trigger", {"type": "manual"}),
            scene=data["scene"],
            fade=FadeSpec.from_dict(data.get("fade")),
        )


class LiveSession:
    def __init__(self, name: str = "", states: list = None):
        self.name = name
        self.states = states if states is not None else []

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": SESSION_VERSION,
            "name": self.name,
            "states": [state.to_dict() for state in self.states],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LiveSession":
        version = data.get("version")
        if version != SESSION_VERSION:
            raise UnknownSessionVersion(
                "Session format version %r is not supported (expected %d)"
                % (version, SESSION_VERSION)
            )
        return cls(
            name=data.get("name", ""),
            states=[SessionState.from_dict(s) for s in data.get("states", [])],
        )

    @classmethod
    def load(cls, path: str) -> "LiveSession":
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidSessionFile(
                "%s is not a valid session file: %s" % (os.path.basename(path), exc)
            )

        return cls.from_dict(data)

    def save(self, path: str) -> None:
        """Atomic write: a failed save never damages the existing file."""
        payload = json.dumps(self.to_dict(), indent=4)

        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    # -- editing ----------------------------------------------------------

    def capture(self, scene: dict, name: str, after_index: int = None) -> int:
        state = SessionState(name, {"type": "manual"}, scene)
        if after_index is None:
            self.states.append(state)
            return len(self.states) - 1

        index = after_index + 1
        self.states.insert(index, state)
        return index

    def overwrite(self, index: int, scene: dict) -> None:
        self.states[index].scene = scene

    def delete(self, index: int) -> None:
        del self.states[index]

    def move(self, from_index: int, to_index: int) -> None:
        state = self.states.pop(from_index)
        self.states.insert(to_index, state)

    def rename(self, index: int, name: str) -> None:
        self.states[index].name = name

    # -- derived ----------------------------------------------------------

    def compute_union(self) -> list:
        """Every node any state uses, one entry per id, first occurrence wins.

        This is the set instantiated at load so all GLSL compiles up front.
        """
        union = {}
        for state in self.states:
            for node in state.scene.get("nodes", []):
                union.setdefault(node["id"], node)
        return list(union.values())
