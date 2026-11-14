# Numeric constants below describe the mjlog wire layout.
# ruff: noqa: PLR2004
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, NamedTuple, NoReturn

from tenhou_converter.melds import DecodedMeld, decode_meld
lazy from tenhou_converter.parser import Event

if TYPE_CHECKING:
    from corpus.models import Expected, Situation


class Action(NamedTuple):
    kind: str
    seat: int
    tile: int


@dataclass
class Player:
    hand: set[int]
    melds: list[DecodedMeld] = field(default_factory=list)
    norths: set[int] = field(default_factory=set)
    draws: int = 0
    discards: int = 0
    riichi: Literal["none", "riichi", "double_riichi"] = "none"
    declared: bool = False
    double: bool = False
    ippatsu: bool = False


@dataclass
class RoundState:
    init: Event
    players: list[Player]
    dealer: int
    remaining: int
    indicators: list[int]
    seen: set[int]
    next_seat: int
    sticks: int
    phase: Literal["draw", "discard", "response"] = "draw"
    last: Action | None = None
    interrupted: bool = False
    supplemental: bool = False
    finished: bool = False
    winners: set[int] = field(default_factory=set)
    indicator_due: int = 0
    results: list[Expected] = field(default_factory=list)

    def check_settlement(self) -> None:
        if not self.results:
            return

        for result in self.results:
            deltas = result["event_score_deltas"] or []
            if any(
                delta > 0 and seat not in self.winners
                for seat, delta in enumerate(deltas)
            ):
                self.fail(self.init, "score gain belongs to a nonwinner")
            # Unknown individual sticks mark shared win-group deltas.
            if (
                result["riichi_stick_points"] is None
                and sum(deltas) != self.sticks * 1000
            ):
                self.fail(
                    self.init,
                    "shared deltas conflict with available riichi sticks",
                )

        sticks = [result["riichi_stick_points"] for result in self.results]
        if (
            all(value is not None for value in sticks)
            and sum(value or 0 for value in sticks) != self.sticks * 1000
        ):
            self.fail(
                self.init,
                "score components conflict with available riichi sticks",
            )

        honba = [result["honba_points"] for result in self.results]
        if (
            all(value is not None for value in honba)
            and sum(value or 0 for value in honba)
            != self.init.numbers("seed")[1] * (len(self.players) - 1) * 100
        ):
            self.fail(self.init, "score components conflict with honba")

    @classmethod
    def start(cls, event: Event, player_count: int) -> RoundState:
        seed = event.numbers("seed")
        cls._check_seed(seed, event, player_count)

        scores = event.numbers("ten")
        cls._check_scores(scores, event, player_count)

        dealer = event.integer("oya")
        if not 0 <= dealer < player_count or dealer != seed[0] % 4:
            reason = "invalid_attribute"
            raise event.error(reason, "dealer conflicts with round", "oya")

        players = []
        seen: set[int] = set()
        for who in range(player_count):
            hand = event.numbers(f"hai{who}")
            cls._check_hand(hand, event, who, seen)
            seen.update(hand)
            players.append(Player(set(hand)))

        state = cls(
            init=event,
            players=players,
            dealer=dealer,
            remaining=70 if player_count == 4 else 55,
            indicators=[seed[5]],
            seen=seen,
            next_seat=dealer,
            sticks=seed[2],
        )

        for value in seen | {seed[5]}:
            state.check_tile(value, event)
        if seed[5] in seen:
            reason = "inconsistent_events"
            raise event.error(reason, "indicator already in hand", "seed")
        state.seen.add(seed[5])
        return state

    @staticmethod
    def _check_seed(seed: list[int], event: Event, player_count: int) -> None:
        if len(seed) != 6:
            reason = "invalid_attribute"
            raise event.error(
                reason, "round seed must contain six values", "seed"
            )
        if not 0 <= seed[0] < 12:
            reason = "invalid_attribute"
            raise event.error(
                reason, "round number outside supported range", "seed"
            )
        if min(seed[1:3]) < 0:
            reason = "invalid_attribute"
            raise event.error(
                reason, "negative honba or riichi stick count", "seed"
            )
        if seed[0] % 4 >= player_count:
            reason = "invalid_attribute"
            raise event.error(
                reason, "round seat outside player count", "seed"
            )
        if any(not 0 <= value < 6 for value in seed[3:5]):
            reason = "invalid_attribute"
            raise event.error(
                reason, "dice value outside supported range", "seed"
            )
        if not 0 <= seed[5] < 136:
            reason = "invalid_attribute"
            raise event.error(
                reason, "initial indicator outside tile range", "seed"
            )

    @staticmethod
    def _check_scores(
        scores: list[int], event: Event, player_count: int
    ) -> None:
        if len(scores) != 4:
            reason = "invalid_attribute"
            raise event.error(
                reason, "round scores must contain four values", "ten"
            )
        if min(scores) < 0:
            reason = "invalid_attribute"
            raise event.error(reason, "negative initial score", "ten")
        if player_count == 3 and (scores[3] or event.text("hai3")):
            reason = "invalid_attribute"
            raise event.error(
                reason, "unused sanma seat has score or initial tiles", "ten"
            )

    @staticmethod
    def _check_hand(
        hand: list[int], event: Event, who: int, seen: set[int]
    ) -> None:
        if len(hand) != 13:
            reason = "inconsistent_events"
            raise event.error(
                reason,
                "initial hand must contain thirteen tiles",
                f"hai{who}",
            )
        if len(set(hand)) != len(hand):
            reason = "inconsistent_events"
            raise event.error(
                reason,
                "duplicated tile in initial hand",
                f"hai{who}",
            )
        if seen.intersection(hand):
            reason = "inconsistent_events"
            raise event.error(
                reason,
                "initial tile already in another player's hand",
                f"hai{who}",
            )

    def check_tile(self, tile136: int, event: Event) -> None:
        if not 0 <= tile136 < 136:
            reason = "invalid_attribute"
            raise event.error(reason, "tile ID outside 136-tile range", "tile")
        if len(self.players) == 3 and 4 <= tile136 < 32:
            reason = "invalid_attribute"
            raise event.error(
                reason, "sanma excludes two through eight man", "tile"
            )

    def player(self, who: int, event: Event) -> Player:
        if not 0 <= who < len(self.players):
            reason = "invalid_attribute"
            raise event.error(reason, "seat outside player count", "who")
        return self.players[who]

    def fail(self, event: Event, message: str) -> NoReturn:
        reason = "inconsistent_events"
        raise event.error(reason, message)

    def interrupt(self) -> None:
        self.interrupted = True
        for player in self.players:
            player.ippatsu = False

    def finish_draw(self, event: Event) -> None:
        reason = event.attributes.get("type")
        if any(
            player.declared
            and (
                reason != "ron3"
                or self.last is None
                or self.last.kind != "discard"
                or self.last.seat != seat
            )
            for seat, player in enumerate(self.players)
        ):
            self.fail(event, "drawn round before riichi confirmation")
        if reason is None and self.remaining != 0:
            self.fail(event, "exhaustive draw before wall exhaustion")
        if reason is not None and reason not in {
            "yao9",
            "reach4",
            "ron3",
            "kan4",
            "kaze4",
            "nm",
        }:
            error_reason = "invalid_attribute"
            raise event.error(
                error_reason, "unknown drawn-round reason", "type"
            )
        ba = event.numbers("ba")
        sc = event.numbers("sc")
        if ba != [self.init.numbers("seed")[1], self.sticks]:
            self.fail(
                event, "drawn-round honba or sticks conflict with progression"
            )
        if len(sc) != 8:
            self.fail(event, "drawn-round scores must contain eight values")
        if len(self.players) == 3 and sc[6:] != [0, 0]:
            self.fail(
                event, "unused sanma seat has drawn-round score or delta"
            )
        self.finished = True

    def draw(self, who: int, tile136: int, event: Event) -> None:
        if any(player.declared for player in self.players):
            self.fail(event, "draw before riichi confirmation")
        self.check_tile(tile136, event)
        player = self.player(who, event)
        if (
            self.phase == "discard"
            or who != self.next_seat
            or self.remaining <= 0
            or tile136 in self.seen
        ):
            self.fail(event, "unexpected or duplicated draw")
        self.supplemental = self.last is not None and self.last.kind in (
            "ankan",
            "daiminkan",
            "kakan",
            "nuki",
        )
        if self.supplemental:
            self.interrupt()
        self.remaining -= 1
        self.seen.add(tile136)
        player.hand.add(tile136)
        player.draws += 1
        self.phase = "discard"
        self.last = Action(kind="draw", seat=who, tile=tile136)

    def discard(self, who: int, tile136: int, event: Event) -> None:
        player = self.player(who, event)
        if (
            self.phase != "discard"
            or who != self.next_seat
            or tile136 not in player.hand
        ):
            self.fail(event, "discard without matching draw or call")
        player.hand.remove(tile136)
        player.discards += 1
        player.ippatsu = False
        self.phase = "response"
        self.next_seat = (who + 1) % len(self.players)
        self.last = Action(kind="discard", seat=who, tile=tile136)

    def reach(self, event: Event) -> None:
        who = event.integer("who")
        player = self.player(who, event)
        step = event.integer("step")
        if step == 1:
            if (
                self.phase != "discard"
                or self.next_seat != who
                or player.declared
                or player.riichi != "none"
                or any(meld.kind != "ankan" for meld in player.melds)
            ):
                self.fail(event, "invalid riichi declaration")
            player.declared = True
            player.double = not self.interrupted and player.discards == 0
        elif step == 2:
            if (
                not player.declared
                or self.last is None
                or self.last.kind != "discard"
                or self.last.seat != who
            ):
                self.fail(
                    event, "riichi confirmation without declaration discard"
                )
            player.declared = False
            player.riichi = "double_riichi" if player.double else "riichi"
            player.ippatsu = True
            self.sticks += 1
        else:
            reason = "invalid_attribute"
            raise event.error(reason, "unknown reach step", "step")

    def call(self, event: Event) -> None:
        if any(player.declared for player in self.players):
            self.fail(event, "call before riichi confirmation")
        who = event.integer("who")
        player = self.player(who, event)
        meld = decode_meld(event.integer("m"), who, event)
        for value in meld.tiles:
            self.check_tile(value, event)
        self.consume_call(meld, who, event)
        if meld.kind == "kakan":
            matches = [
                index
                for index, old in enumerate(player.melds)
                if old.kind == "pon"
                and old.tiles == meld.tiles[:3]
                and old.source == meld.source
                and old.called == meld.called
            ]
            if len(matches) != 1:
                self.fail(event, "added kan has no matching pon")
            player.melds[matches[0]] = meld
        elif meld.kind == "nuki":
            player.norths.add(meld.tiles[0])
        else:
            player.melds.append(meld)
        supplemental = meld.kind not in ("chii", "pon")
        if supplemental and self.remaining <= 0:
            self.fail(event, "no tiles remain for supplemental draw")
        if supplemental and meld.kind != "nuki":
            self.indicator_due += 1
        self.phase = "draw" if supplemental else "discard"
        self.next_seat = who
        self.last = Action(
            kind=meld.kind,
            seat=who,
            tile=meld.tiles[-1] if meld.kind == "kakan" else meld.tiles[0],
        )

    def consume_call(self, meld: DecodedMeld, who: int, event: Event) -> None:
        player = self.player(who, event)
        if meld.kind in ("chii", "pon", "daiminkan"):
            if (
                self.last is None
                or self.last.kind != "discard"
                or self.phase != "response"
                or meld.called is None
                or self.last.seat != meld.source
                or self.last.tile != meld.tiles[meld.called]
            ):
                self.fail(event, "call does not match discarded tile")
            if len(self.players) == 3 and (
                meld.kind == "chii" or meld.source == 3
            ):
                self.fail(event, "invalid sanma call")
            consumed = [
                value
                for index, value in enumerate(meld.tiles)
                if index != meld.called
            ]
            self.interrupt()
        else:
            if (
                self.phase != "discard"
                or self.next_seat != who
                or self.last is None
                or self.last.kind != "draw"
            ):
                self.fail(event, "self call without draw")
            consumed = (
                meld.tiles
                if meld.kind in ("ankan", "nuki")
                else meld.tiles[-1:]
            )
            if meld.kind == "nuki" and len(self.players) != 3:
                self.fail(event, "invalid north extraction")
            if meld.kind == "ankan":
                self.interrupt()
        if not set(consumed) <= player.hand:
            self.fail(event, "call consumes tiles absent from hand")
        player.hand.difference_update(consumed)

    def dora(self, event: Event) -> None:
        value = event.integer("hai")
        self.check_tile(value, event)
        if (
            not self.indicator_due
            or value in self.seen
            or len(self.indicators) >= 5
        ):
            self.fail(event, "unexpected dora indicator")
        self.indicator_due -= 1
        self.indicators.append(value)
        self.seen.add(value)

    def situation(self, event: Event) -> Situation:
        who = event.integer("who")
        source = event.integer("fromWho")
        player = self.player(who, event)
        self.player(source, event)
        winning = event.integer("machi")
        tsumo = who == source
        valid = ("draw",) if tsumo else ("discard", "kakan", "nuki")
        if (
            self.last is None
            or self.last.kind not in valid
            or self.last.seat != source
            or self.last.tile != winning
            or who in self.winners
            or len(self.winners) >= 2
            or (tsumo and self.winners)
        ):
            self.fail(event, "win does not match tile provider")
        if any(
            other.declared
            and (tsumo or seat != source or self.last.kind != "discard")
            for seat, other in enumerate(self.players)
        ):
            self.fail(event, "win before riichi confirmation")
        self._check_agari_tiles(event, who, winning, tsumo=tsumo)

        last_kind = self.last.kind
        first_uninterrupted_draw = (
            tsumo and player.draws == 1 and not self.interrupted
        )
        return {
            "tsumo": tsumo,
            "riichi": player.riichi,
            "ippatsu": player.ippatsu,
            "rinshan": tsumo and self.supplemental,
            "chankan": not tsumo and last_kind in ("kakan", "nuki"),
            "haitei": tsumo and self.remaining == 0 and not self.supplemental,
            "houtei": not tsumo
            and self.remaining == 0
            and last_kind == "discard",
            "tenhou": first_uninterrupted_draw and who == self.dealer,
            "chiihou": first_uninterrupted_draw and who != self.dealer,
            "renhou": False,
        }

    def _check_agari_tiles(
        self, event: Event, who: int, winning: int, *, tsumo: bool
    ) -> None:
        """Check recorded tiles against the reconstructed round."""
        player = self.players[who]
        hand = event.numbers("hai")
        actual = player.hand if tsumo else player.hand | {winning}
        if len(set(hand)) != len(hand) or set(hand) != actual:
            self.fail(event, "AGARI hand differs from reconstructed hand")

        melds = (
            [decode_meld(code, who, event) for code in event.numbers("m")]
            if "m" in event.attributes
            else []
        )
        norths = [meld.tiles[0] for meld in melds if meld.kind == "nuki"]
        regular = [meld for meld in melds if meld.kind != "nuki"]
        if (
            len(set(norths)) != len(norths)
            or set(norths) != player.norths
            or sorted(regular, key=lambda meld: meld.tiles)
            != sorted(player.melds, key=lambda meld: meld.tiles)
        ):
            self.fail(event, "AGARI calls differ from reconstructed calls")

        if event.numbers("doraHai") != self.indicators:
            self.fail(event, "AGARI dora differs from revealed indicators")
