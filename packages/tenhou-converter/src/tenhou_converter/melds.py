# Numeric constants below describe the mjlog wire layout.
# ruff: noqa: PLR2004
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NoReturn, cast

lazy from tenhou_converter.parser import Event

if TYPE_CHECKING:
    from corpus.models import Meld, Tile

MeldKind = Literal["chii", "pon", "daiminkan", "ankan", "kakan", "nuki"]


def tile(value: int) -> Tile:
    if value in (16, 52, 88):
        return cast("Tile", "0" + "mps"[value // 36])
    kind = value // 4
    return cast("Tile", f"{kind % 9 + 1}{'mpsz'[kind // 9]}")


@dataclass(frozen=True)
class DecodedMeld:
    kind: MeldKind
    tiles: list[int]
    called: int | None
    source: int | None

    def corpus_value(self) -> Meld:
        if self.kind == "nuki":
            msg = "north extraction is not a regular meld"
            raise ValueError(msg)
        return {
            "type": self.kind,
            "tiles": [tile(value) for value in self.tiles],
            "called_tile_index": self.called,
            "from_seat": self.source,
        }


def decode_meld(code: int, who: int, event: Event) -> DecodedMeld:  # noqa: C901 -- five protocol layouts, ordered by flag precedence
    def invalid() -> NoReturn:
        reason = "unknown_meld_code"
        raise event.error(reason, f"invalid meld code {code}", "m")

    # Meld codes are unsigned 16-bit integers; bit 0 is the least
    # significant bit.
    if not 0 <= code < 65536:
        invalid()
    # Bits 0-1 (0x0003): source seat relative to the caller; 0 means
    # self.
    # The wire format uses four seat slots even in three-player games.
    relative = code & 3
    source = (who + relative) % 4
    # Bit 2 (0x0004): chii. Decode this layout before the other flags.
    if code & 4:
        # Bits 10-15: sequence index * 3 + called tile's index in the
        # sequence.
        pattern = code >> 10
        # There are 3 suits * 7 sequences * 3 called positions = 63
        # patterns.
        # Chii must come from the previous seat; bit 9 (0x0200) is
        # unused.
        if pattern >= 63 or relative != 3 or code & 0x0200:
            invalid()
        sequence = pattern // 3
        # Map the suit and sequence start to the first physical tile ID.
        base = (sequence // 7 * 9 + sequence % 7) * 4
        # Bits 3-4: copy index (0-3) of the sequence's first tile.
        # Bits 5-6: copy index (0-3) of the sequence's second tile.
        # Bits 7-8: copy index (0-3) of the sequence's third tile.
        tiles = [
            base + offset * 4 + ((code >> (3 + 2 * offset)) & 3)
            for offset in range(3)
        ]
        return DecodedMeld("chii", tiles, pattern % 3, source)
    # Bit 3 (0x0008): pon.
    # Bit 4 (0x0010): kakan.
    # These flags take precedence over bit 5, which is tile data in this
    # layout.
    if code & 0x18:
        # Bits 9-15: tile kind * 3 + called tile's index in the original
        # pon.
        pattern = code >> 9
        # Require one of 34 * 3 patterns and a source other than self.
        # Bits 7-8 (0x0180) are unused; pon and kakan flags are mutually
        # exclusive.
        if (
            pattern >= 102
            or not relative
            or code & 0x180
            or code & 0x18 == 0x18
        ):
            invalid()
        # Bits 5-6: copy index omitted from the original pon (added for
        # kakan).
        omitted = (code >> 5) & 3
        base = pattern // 3 * 4
        # Keep copies in wire order so pattern % 3 identifies the called
        # tile.
        tiles = [base + offset for offset in range(4) if offset != omitted]
        kind: MeldKind = "pon" if code & 8 else "kakan"
        if kind == "kakan":
            # Append the added tile without changing the original pon's
            # indices.
            tiles.append(base + omitted)
        return DecodedMeld(kind, tiles, pattern % 3, source)
    # Bit 5 (0x0020): north extraction when no chii/pon/kakan flag
    # matched.
    if code & 0x20:
        # Bits 0-7 must contain only the extraction flag.
        # Bits 8-15 contain the physical tile ID, restricted to north
        # (120-123).
        if code & 0xFF != 0x20 or code >> 8 not in range(120, 124):
            invalid()
        return DecodedMeld("nuki", [code >> 8], None, None)
    # With no preceding flag, the layout represents ankan or daiminkan.
    # Bits 8-15 contain a physical tile ID of the kan's tile kind.
    # For daiminkan, this is the called tile; for ankan, it has no
    # called role.
    called = code >> 8
    # Physical tile IDs range from 0 to 135; bits 2-7 (0x00FC) are
    # unused.
    if called >= 136 or code & 0xFC:
        invalid()
    # All four physical copies belong to the kan, in ascending ID order.
    tiles = list(range(called // 4 * 4, called // 4 * 4 + 4))
    # A nonzero relative source means daiminkan; self means ankan.
    return DecodedMeld(
        "daiminkan" if relative else "ankan",
        tiles,
        called % 4 if relative else None,
        source if relative else None,
    )
