from typing import Literal

from tenhou_converter.errors import UnsupportedLogError
lazy from tenhou_converter.parser import Event


def player_count(go: Event) -> Literal[3, 4]:
    value = go.integer("type")
    if value < 0 or value & ~0xFFF:
        reason = "invalid_attribute"
        raise go.error(reason, "unknown GO type bits", "type")
    if not value & 1 or value & 0xF06 or go.integer("lobby") != 0:
        reason = "unsupported_rules"
        raise UnsupportedLogError(
            reason,
            "only ranked aka/kuitan games are supported",
            event_index=go.index,
            field="type",
        )
    return 3 if value & 0x10 else 4
