from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtQuickWidgets import QQuickWidget

from zilo_ring.domain import MotionEstimate, Orientation


class RingView(QQuickWidget):
    """Interactive 3D scene; IMU changes orientation, never scene position."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._orientation = Orientation()
        self.setMinimumSize(560, 420)
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        scene_path = Path(__file__).with_name("ring_scene.qml")
        self.setSource(QUrl.fromLocalFile(str(scene_path)))

        if self.status() == QQuickWidget.Status.Error:
            details = "\n".join(error.toString() for error in self.errors())
            raise RuntimeError(f"Unable to load ring 3D scene:\n{details}")

    def set_orientation(self, orientation: Orientation) -> None:
        self._orientation = orientation
        root = self.rootObject()
        if root is None:
            return
        root.setProperty("ringRoll", orientation.roll_deg)
        root.setProperty("ringPitch", orientation.pitch_deg)
        root.setProperty("ringYaw", orientation.yaw_deg)

    def set_motion(self, motion: MotionEstimate) -> None:
        root = self.rootObject()
        if root is None:
            return
        direction = motion.direction_vector
        root.setProperty("motionX", direction.x)
        root.setProperty("motionY", direction.y)
        root.setProperty("motionZ", direction.z)
        root.setProperty("motionIntensity", motion.intensity_g)
        root.setProperty("motionConfidence", motion.confidence)
        root.setProperty("motionDirection", motion.direction.value)
        root.setProperty("motionPhase", motion.phase.value)
