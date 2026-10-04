# Stable instructions

1. Keep the application single-ring unless the user explicitly changes scope.
2. Preserve dependency direction: presentation -> application -> ports/domain; infrastructure implements ports; bootstrap wires concrete objects.
3. Qt code must not import the OpenZilo SDK or Bleak adapter directly.
4. Bluetooth code must not import Qt.
5. Keep raw IMU values, physical units, device timestamps, receive timestamps, and sequence numbers distinct.
6. Do not present acceleration integration as real position. The ring has a fixed scene position; only the camera may orbit, pan, or zoom.
7. Treat fresh IMU samples, not a live process, as proof of an active connection.
8. Prefer a bounded latest-value path over unbounded queues. Old display frames may be dropped.
9. Keep device sample rate, receive rate, and render rate conceptually separate.
10. Add tests around pure layers before hardware testing. Never claim hardware behavior without a live test.
11. Do not commit or push unless the user asks.
