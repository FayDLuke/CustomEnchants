"""Minimal fake of the `endstone` package, just enough to import and unit-test the plugin's pure logic
(storage, constants, item classification, manager registration, engine gather/toggle bookkeeping)
without a real Bedrock Dedicated Server. This is NOT a behavioural simulator of Minecraft."""
from __future__ import annotations

import uuid as _uuid


class Actor:
    def __init__(self, name="actor"):
        self.id = id(self)
        self.name = name
        self.name_tag = ""
        self.is_dead = False
        self.is_valid = True
        self.health = 20
        self.max_health = 20
        self.velocity = Vector3Stub(0, 0, 0)
        self.location = None
        self.dimension = None
        self.scoreboard_tags = set()

    def add_scoreboard_tag(self, tag):
        self.scoreboard_tags.add(tag)
        return True

    def remove_scoreboard_tag(self, tag):
        self.scoreboard_tags.discard(tag)
        return True

    def teleport(self, location):
        self.location = location
        return True

    def remove(self):
        self.is_dead = True
        self.is_valid = False


class Vector3Stub:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class Player(Actor):
    def __init__(self, name="Steve"):
        super().__init__(name)
        self.unique_id = _uuid.uuid4()
        self.is_sneaking = False
        self.is_sprinting = False
        self.is_on_ground = True
        self.allow_flight = False
        self.inventory = None
        self._messages = []

    def send_message(self, msg):
        self._messages.append(str(msg))

    def send_tip(self, msg):
        self._messages.append(str(msg))

    def send_popup(self, msg):
        self._messages.append(str(msg))

    def has_permission(self, name):
        return True

    def send_form(self, form):
        pass

    def send_packet(self, packet_id, payload):
        pass
