"""Reconstruct the state used by the scoring input."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from majsoul_converter.decoder import ConversionError
from majsoul_converter.liqi import liqi_pb2 as pb

if TYPE_CHECKING:
    from google.protobuf.message import Message

_OPEN_KAN = 2
_MELD_TYPES = {0: "chii", 1: "pon", _OPEN_KAN: "daiminkan"}
_ADDED_KAN = 2
_CLOSED_KAN = 3
_THREE_PLAYERS = 3
_WIND_COUNT = 4
_KAN_TILES = 4


def _kind(tile: str) -> str:
    return "5" + tile[1:] if tile.startswith("0") else tile


def _is_replacement_draw(previous: Message) -> bool:
    match previous:
        case pb.RecordAnGangAddGang() | pb.RecordBaBei():
            return True
        case pb.RecordChiPengGang():
            return previous.type == _OPEN_KAN
    return False


def _matches_tsumo(previous: Message, win: pb.HuleInfo) -> bool:
    match previous:
        case pb.RecordDealTile():
            return previous.seat == win.seat and previous.tile == win.hu_tile
        case pb.RecordNewRound():
            return previous.ju == win.seat
    return False


@dataclass
class Meld:
    type: str
    tiles: list[str]
    called_tile_index: int | None = None
    from_seat: int | None = None


@dataclass
class Player:
    hand: list[str]
    melds: list[Meld] = field(default_factory=list)
    nuki: int = 0
    riichi: str = "none"
    ippatsu: bool = False
    discarded: bool = False


class RoundState:
    def __init__(self, event: pb.RecordNewRound, index: int) -> None:
        self.start = event
        self.event_indices = [index]
        self.count = len(event.scores)
        if (
            self.count not in (3, 4)
            or event.ju >= self.count
            or event.chang >= _WIND_COUNT
        ):
            msg = "invalid player count, dealer or round wind"
            raise ConversionError(msg)
        hands = (event.tiles0, event.tiles1, event.tiles2, event.tiles3)
        if any(hands[self.count :]):
            msg = "initial hand recorded for an inactive seat"
            raise ConversionError(msg)
        self.players = [Player(list(tiles)) for tiles in hands[: self.count]]
        self.sticks = event.liqibang
        self.last: Message = event
        self.interrupted = False
        self.rinshan = False
        self.last_tile = False
        self.doras = list(event.doras) or ([event.dora] if event.dora else [])

    def _interrupt(self) -> None:
        self.interrupted = True
        for player in self.players:
            player.ippatsu = False

    def _open_meld(self, event: pb.RecordChiPengGang, player: Player) -> None:
        kind = _MELD_TYPES[event.type]
        tiles = list(event.tiles)
        (called,) = (
            i for i, seat in enumerate(event.froms) if seat != event.seat
        )
        from_seat = event.froms[called]
        msg = "call does not match the preceding discard"
        if len(tiles) != len(event.froms):
            raise ConversionError(msg)
        discard = self.last
        if not isinstance(discard, pb.RecordDiscardTile):
            raise ConversionError(msg)
        if (from_seat, tiles[called]) != (discard.seat, discard.tile):
            raise ConversionError(msg)

        for index, tile in enumerate(tiles):
            if index != called:
                player.hand.remove(tile)
        player.melds.append(Meld(kind, tiles, called, from_seat))

    def _kan(self, event: pb.RecordAnGangAddGang, player: Player) -> None:
        kind = _kind(event.tiles)
        tiles = [tile for tile in player.hand if _kind(tile) == kind]
        if event.type == _CLOSED_KAN and len(tiles) == _KAN_TILES:
            player.melds.append(Meld("ankan", tiles))
        elif event.type == _ADDED_KAN and len(tiles) == 1:
            (meld,) = (
                meld
                for meld in player.melds
                if meld.type == "pon" and _kind(meld.tiles[0]) == kind
            )
            meld.type = "kakan"
            meld.tiles.extend(tiles)
        else:
            msg = "kan does not match the concealed tiles"
            raise ConversionError(msg)

        for tile in tiles:
            player.hand.remove(tile)

    def advance(self, event: Message) -> None:
        match event:
            case pb.RecordDealTile() | pb.RecordChiPengGang():
                if event.HasField("liqi") and not event.liqi.failed:
                    self.sticks = event.liqi.liqibang

        match event:
            case pb.RecordDealTile():
                self.players[event.seat].hand.append(event.tile)
                self.rinshan = _is_replacement_draw(self.last)
                self.last_tile = event.left_tile_count == 0
            case pb.RecordDiscardTile():
                player = self.players[event.seat]
                player.hand.remove(event.tile)
                player.ippatsu = event.is_liqi or event.is_wliqi
                if player.ippatsu:
                    player.riichi = (
                        "double_riichi" if event.is_wliqi else "riichi"
                    )
                player.discarded = True
            case pb.RecordChiPengGang():
                self._open_meld(event, self.players[event.seat])
                self._interrupt()
            case pb.RecordAnGangAddGang():
                self._kan(event, self.players[event.seat])
                self._interrupt()
            case pb.RecordBaBei() if self.count == _THREE_PLAYERS:
                player = self.players[event.seat]
                player.hand.remove("4z")
                player.nuki += 1
                self._interrupt()
            case _:
                msg = f"unsupported replay event {type(event).__name__}"
                raise ConversionError(msg)

        if not isinstance(event, pb.RecordChiPengGang) and event.doras:
            self.doras = list(event.doras)
        self.last = event

    def win_input(
        self, win: pb.HuleInfo, result: pb.RecordHule
    ) -> tuple[dict[str, object], int | None]:
        player = self.players[win.seat]
        last = self.last
        hand = list(win.hand)
        # HuleInfo.hand omits the winning tile for both tsumo and ron.
        if win.zimo:
            if not _matches_tsumo(last, win):
                msg = "tsumo does not match the preceding draw"
                raise ConversionError(msg)
            recorded_hand = [*hand, win.hu_tile]
            payer = None
        else:
            payer = self._ron_source(win.hu_tile)
            recorded_hand = hand

        if sorted(player.hand) != sorted(recorded_hand):
            msg = "reconstructed hand differs from the win record"
            raise ConversionError(msg)

        first_draw = win.zimo and not self.interrupted and not player.discarded
        chankan = isinstance(last, pb.RecordAnGangAddGang)
        robbed_north = isinstance(last, pb.RecordBaBei)
        return {
            "winner_seat": win.seat,
            "discarder_seat": payer,
            "concealed_tiles": hand,
            "winning_tile": win.hu_tile,
            "melds": [
                {
                    "type": meld.type,
                    "tiles": meld.tiles.copy(),
                    "called_tile_index": meld.called_tile_index,
                    "from_seat": meld.from_seat,
                }
                for meld in player.melds
            ],
            "nuki_count": player.nuki,
            "dora_indicators": list(win.doras or result.doras) or self.doras,
            "ura_dora_indicators": list(win.li_doras),
            "situation": {
                "tsumo": win.zimo,
                "riichi": player.riichi,
                "ippatsu": player.ippatsu,
                "rinshan": win.zimo and self.rinshan,
                "chankan": chankan,
                "haitei": win.zimo and self.last_tile and not self.rinshan,
                "houtei": not win.zimo
                and self.last_tile
                and not (chankan or robbed_north),
                "tenhou": first_draw and win.seat == self.start.ju,
                "chiihou": first_draw and win.seat != self.start.ju,
                "renhou": False,
            },
        }, payer

    def _ron_source(self, tile: str) -> int:
        match self.last:
            case pb.RecordDiscardTile() as event if event.tile == tile:
                return event.seat
            case pb.RecordAnGangAddGang() as event if _kind(
                event.tiles
            ) == _kind(tile):
                return event.seat
            case pb.RecordBaBei() as event if tile == "4z":
                return event.seat
        msg = "ron does not match the preceding discard, kan or nuki"
        raise ConversionError(msg)
