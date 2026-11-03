from typing import Literal

from tenhou_converter.errors import UnsupportedLogError
from tenhou_converter.parser import Event


def player_count(go: Event) -> Literal[3, 4]:
    value = go.integer("type")
    if value < 0 or value & ~0xFFF:
        msg = "invalid_attribute"
        raise go.error(msg, "unknown GO type bits", "type")
    if not value & 1 or value & 0xF06 or go.integer("lobby") != 0:
        msg = "unsupported_rules"
        raise UnsupportedLogError(
            msg,
            "only ranked aka/kuitan games are supported",
            event_index=go.index,
            field="type",
        )
    return 3 if value & 0x10 else 4
