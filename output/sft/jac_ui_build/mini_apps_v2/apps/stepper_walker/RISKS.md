# Risks (constructs not found in a verified app)

1. components/RoomPanel.jac line 61: the string `" °C"` contains a non-ASCII character (degree sign). No verified app has a non-ASCII literal in Jac source; based on Jac strings being UTF-8. The flow text "20 °C" depends on it (a normal space, not a non-breaking one).
2. services/room.jac: four walkers share the same `start` ability copy (create-if-missing, then visit); the pattern is counter_walker's, repeated per walker. A walker (reset_room) that assigns a constant instead of incrementing is the only new logic.
3. components/RoomPanel.jac: three async handlers each doing `root spawn` in the same component; counter_walker has one. No new syntax.
