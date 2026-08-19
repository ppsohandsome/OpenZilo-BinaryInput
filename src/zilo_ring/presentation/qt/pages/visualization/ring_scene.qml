import QtQuick
import QtQuick3D
import QtQuick3D.Helpers

Rectangle {
    id: root
    color: "#111820"

    property real ringRoll: 0
    property real ringPitch: 0
    property real ringYaw: 0
    property real motionX: 0
    property real motionY: 0
    property real motionZ: 0
    property real motionIntensity: 0
    property real motionConfidence: 0
    property string motionDirection: "NONE"
    property string motionPhase: "IDLE"
    readonly property vector3d motionSceneDirection: Qt.vector3d(motionX, motionZ, -motionY)
    readonly property real motionDisplayLength: 145 + Math.min(1.0, motionIntensity) * 135

    function motionRotation() {
        const direction = motionSceneDirection
        const magnitude = Math.sqrt(direction.x * direction.x
            + direction.y * direction.y + direction.z * direction.z)
        if (magnitude < 0.0001)
            return Quaternion.fromAxisAndAngle(Qt.vector3d(1, 0, 0), 0)
        const dx = direction.x / magnitude
        const dy = direction.y / magnitude
        const dz = direction.z / magnitude
        const axisLength = Math.sqrt(dx * dx + dz * dz)
        if (axisLength < 0.0001)
            return Quaternion.fromAxisAndAngle(Qt.vector3d(1, 0, 0), dy >= 0 ? 0 : 180)
        const angle = Math.acos(Math.max(-1, Math.min(1, dy))) * 180 / Math.PI
        return Quaternion.fromAxisAndAngle(Qt.vector3d(dz / axisLength, 0, -dx / axisLength), angle)
    }

    component AxisArrow: Node {
        id: arrow
        property color axisColor: "white"
        property real length: 175

        Model {
            position: Qt.vector3d(0, arrow.length * 0.42, 0)
            scale: Qt.vector3d(0.055, arrow.length * 0.0084, 0.055)
            source: "#Cylinder"
            materials: DefaultMaterial {
                diffuseColor: arrow.axisColor
                lighting: DefaultMaterial.NoLighting
            }
        }
        Model {
            position: Qt.vector3d(0, arrow.length * 0.90, 0)
            scale: Qt.vector3d(0.13, 0.28, 0.13)
            source: "#Cone"
            materials: DefaultMaterial {
                diffuseColor: arrow.axisColor
                lighting: DefaultMaterial.NoLighting
            }
        }
    }

    component DirectionCell: Rectangle {
        required property string directionName
        required property string label
        readonly property bool selected: root.motionDirection === directionName
        width: 68
        height: 25
        radius: 3
        color: selected
            ? (root.motionPhase === "BRAKING" ? "#8b612a" : "#176f7b")
            : "#17232d"
        border.color: selected ? "#55dce2" : "#2d404f"

        Text {
            anchors.centerIn: parent
            text: parent.label
            color: parent.selected ? "#e9feff" : "#718696"
            font.pixelSize: 9
            font.bold: parent.selected
        }
    }

    View3D {
        id: scene
        anchors.fill: parent
        camera: cameraNode

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: root.color
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        Node {
            id: cameraOrigin
            y: 75
            eulerRotation: Qt.vector3d(-18, -28, 0)

            PerspectiveCamera {
                id: cameraNode
                z: 620
                clipNear: 5
                clipFar: 5000
            }
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-38, -32, 0)
            brightness: 1.2
            ambientColor: Qt.rgba(0.22, 0.27, 0.32, 1)
        }
        PointLight {
            position: Qt.vector3d(-220, 300, 260)
            brightness: 40
            color: "#8fc8ff"
        }

        AxisHelper {
            enableAxisLines: false
            enableXZGrid: true
            gridColor: "#607181"
            gridOpacity: 0.25
        }

        Node {
            id: sensorNode
            y: 82
            eulerRotation: Qt.vector3d(root.ringRoll, root.ringPitch, root.ringYaw)

            Model {
                geometry: TorusGeometry {
                    radius: 105
                    tubeRadius: 26
                    rings: 64
                    segments: 28
                }
                materials: PrincipledMaterial {
                    baseColor: "#4b91b8"
                    metalness: 0.72
                    roughness: 0.24
                    clearcoatAmount: 0.35
                }
            }

            // The marker is exactly on the positive sensor-X/ring intersection.
            Model {
                x: 140
                geometry: SphereGeometry {
                    radius: 12
                    rings: 16
                    segments: 24
                }
                materials: PrincipledMaterial {
                    baseColor: "#f4b73f"
                    metalness: 0.15
                    roughness: 0.3
                    emissiveFactor: Qt.vector3d(0.12, 0.07, 0.01)
                }
            }

            AxisArrow {
                axisColor: "#ff5c5c"
                length: 215
                eulerRotation.z: -90
            }
            AxisArrow {
                axisColor: "#58d68d"
            }
            AxisArrow {
                axisColor: "#5dade2"
                eulerRotation.x: 90
            }
        }

        // World/control-frame gesture direction. This is not position or velocity.
        Node {
            id: motionVector
            y: 82
            visible: root.motionPhase !== "IDLE"
            opacity: root.motionPhase === "BRAKING" ? 0.48 : 0.84
            rotation: root.motionRotation()

            Model {
                position: Qt.vector3d(0, root.motionDisplayLength * 0.85, 0)
                scale: Qt.vector3d(1, 1.7, 1)
                geometry: ConeGeometry {
                    length: root.motionDisplayLength
                    bottomRadius: 10 + (1.0 - root.motionConfidence) * 22
                    topRadius: 0
                    rings: 2
                    segments: 28
                }
                materials: PrincipledMaterial {
                    baseColor: "#36d3da"
                    metalness: 0.12
                    roughness: 0.25
                    emissiveFactor: Qt.vector3d(0.03, 0.18, 0.20)
                }
            }
        }
    }

    OrbitCameraController {
        anchors.fill: parent
        origin: cameraOrigin
        camera: cameraNode
        panEnabled: true
        xSpeed: 0.22
        ySpeed: 0.22
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 14
        width: orientationText.width + 24
        height: 78
        radius: 5
        color: "#b30c131a"
        border.color: "#334655"

        Text {
            id: orientationText
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 12
            color: "#d7e1ea"
            font.family: "monospace"
            font.pixelSize: 12
            text: "roll  " + root.ringRoll.toFixed(2).padStart(7) + "°   "
                + "pitch " + root.ringPitch.toFixed(2).padStart(7) + "°   "
                + "yaw* " + root.ringYaw.toFixed(2).padStart(7) + "°"
        }
        Row {
            anchors.left: orientationText.left
            anchors.top: orientationText.bottom
            anchors.topMargin: 12
            spacing: 14

            Text { text: "SENSOR"; color: "#91a5b5"; font.pixelSize: 11 }
            Text { text: "X"; color: "#ff5c5c"; font.bold: true }
            Text { text: "Y"; color: "#58d68d"; font.bold: true }
            Text { text: "Z"; color: "#5dade2"; font.bold: true }
            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: "#f4b73f"
                anchors.verticalCenter: parent.verticalCenter
            }
            Text { text: "WEAR MARK"; color: "#e8c66f"; font.pixelSize: 11 }
        }
    }

    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 14
        width: 92
        height: 92
        radius: 46
        color: "#b30c131a"
        border.color: "#334655"

        Canvas {
            anchors.fill: parent
            onPaint: {
                const ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                function arrow(x1, y1, x2, y2, color, label) {
                    const angle = Math.atan2(y2 - y1, x2 - x1)
                    ctx.strokeStyle = color
                    ctx.fillStyle = color
                    ctx.lineWidth = 2
                    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(x2, y2)
                    ctx.lineTo(x2 - 8 * Math.cos(angle - 0.45), y2 - 8 * Math.sin(angle - 0.45))
                    ctx.lineTo(x2 - 8 * Math.cos(angle + 0.45), y2 - 8 * Math.sin(angle + 0.45))
                    ctx.closePath(); ctx.fill()
                    ctx.font = "bold 11px sans-serif"
                    ctx.fillText(label, x2 + 4, y2 - 3)
                }
                arrow(43, 51, 75, 51, "#ff5c5c", "X")
                arrow(43, 51, 43, 18, "#58d68d", "Y")
                arrow(43, 51, 20, 71, "#5dade2", "Z")
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 5
            text: "WORLD"
            color: "#8497a7"
            font.pixelSize: 9
        }
    }

    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: 14
        anchors.topMargin: 116
        width: 164
        height: 137
        radius: 5
        color: "#b30c131a"
        border.color: "#334655"

        Text {
            id: motionTitle
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 10
            text: root.motionDirection === "NONE"
                ? "MOTION · IDLE"
                : "MOTION · " + root.motionDirection
            color: root.motionDirection === "NONE" ? "#8093a3" : "#67e1e5"
            font.pixelSize: 10
            font.bold: true
        }
        Text {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            text: Math.round(root.motionConfidence * 100) + "%"
            color: "#91a5b5"
            font.family: "monospace"
            font.pixelSize: 10
        }
        Grid {
            anchors.left: parent.left
            anchors.top: motionTitle.bottom
            anchors.margins: 10
            columns: 2
            spacing: 4

            DirectionCell { directionName: "UP"; label: "UP" }
            DirectionCell { directionName: "DOWN"; label: "DOWN" }
            DirectionCell { directionName: "LEFT"; label: "LEFT" }
            DirectionCell { directionName: "RIGHT"; label: "RIGHT" }
            DirectionCell { directionName: "FORWARD"; label: "FORWARD" }
            DirectionCell { directionName: "BACK"; label: "BACK" }
        }
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: helpText.width + 24
        height: 28
        radius: 4
        color: "#b30c131a"
        Text {
            id: helpText
            anchors.centerIn: parent
            text: "Drag: orbit   Ctrl+drag: pan   Wheel: zoom   |   fixed visual position"
            color: "#879aaa"
            font.pixelSize: 10
        }
    }
}
