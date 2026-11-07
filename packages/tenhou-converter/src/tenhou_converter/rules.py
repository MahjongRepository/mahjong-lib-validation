from typing import Literal

from tenhou_converter.errors import UnsupportedLogError
lazy from tenhou_converter.parser import Event


def player_count(go: Event) -> Literal[3, 4]:
    value = go.integer("type")
    # Bits are numbered from 0 (the least significant bit).
    # 0xFFF covers known bits 0-11;
    # ~0xFFF detects unknown bits 12 and above.
    if value < 0 or value & ~0xFFF:
        reason = "invalid_attribute"
        raise go.error(reason, "unknown GO type bits", "type")
    # Bit 0 (0x001): 1 for human opponents, 0 for computer opponents.
    # 0xF06 masks unsupported flags (each enabled when its bit is 1):
    # Bit 1 (0x002): no red fives.
    # Bit 2 (0x004): no open tanyao.
    # Bit 8 (0x100): darken tsumogiri.
    # Bit 9 (0x200): shugi bonuses.
    # Bit 10 (0x400): jansou (parlor) matches.
    # Bit 11 (0x800): skill matches.
    if not value & 1 or value & 0xF06 or go.integer("lobby") != 0:
        reason = "unsupported_rules"
        raise UnsupportedLogError(
            reason,
            "only ranked aka/kuitan games are supported",
            event_index=go.index,
            field="type",
        )
    # Bit 4 (0x010): 1 for three players, 0 for four players.
    return 3 if value & 0x10 else 4
