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

    if not 0 <= code < 65536:
        invalid()
    relative = code & 3
    source = (who + relative) % 4
    if code & 4:
        pattern = code >> 10
        if pattern >= 63 or relative != 3 or code & 0x0200:
            invalid()
        sequence = pattern // 3
        base = (sequence // 7 * 9 + sequence % 7) * 4
        tiles = [
            base + offset * 4 + ((code >> (3 + 2 * offset)) & 3)
            for offset in range(3)
        ]
        return DecodedMeld("chii", tiles, pattern % 3, source)
    if code & 0x18:
        pattern = code >> 9
        if (
            pattern >= 102
            or not relative
            or code & 0x180
            or code & 0x18 == 0x18
        ):
            invalid()
        omitted = (code >> 5) & 3
        base = pattern // 3 * 4
        tiles = [base + offset for offset in range(4) if offset != omitted]
        kind: MeldKind = "pon" if code & 8 else "kakan"
        if kind == "kakan":
            tiles.append(base + omitted)
        return DecodedMeld(kind, tiles, pattern % 3, source)
    if code & 0x20:
        if code & 0xFF != 0x20 or code >> 8 not in range(120, 124):
            invalid()
        return DecodedMeld("nuki", [code >> 8], None, None)
    called = code >> 8
    if called >= 136 or code & 0xFC:
        invalid()
    tiles = list(range(called // 4 * 4, called // 4 * 4 + 4))
    return DecodedMeld(
        "daiminkan" if relative else "ankan",
        tiles,
        called % 4 if relative else None,
        source if relative else None,
    )
