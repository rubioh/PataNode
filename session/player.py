"""Drives a live session against a scene.

Union model: every node any state uses is instantiated once at load, so all
GLSL compiles up front. A state then only rewires edges and applies
parameter values -- no construction, no compilation, no hitch mid-set.
"""

import copy

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
