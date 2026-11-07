# Numeric constants below describe the mjlog wire layout.
# ruff: noqa: PLR2004
import re
from urllib.parse import quote

from corpus import CorpusError, ScoringCase, parse_case

from tenhou_converter.errors import ConversionError
from tenhou_converter.melds import decode_meld, tile
from tenhou_converter.parser import Event, parse_xml
from tenhou_converter.reconstruction import RoundState
from tenhou_converter.rules import player_count
from tenhou_converter.scoring import expected_values

METADATA = frozenset({"SHUFFLE", "UN", "TAIKYOKU", "BYE"})


def multiple_ron_indices(events: list[Event]) -> set[int]:
    result: set[int] = set()
    current: list[int] = []
    for event in events:
        if event.tag == "INIT":
            if len(current) > 1:
                result.update(current)
            current = []
        elif event.tag == "AGARI":
            current.append(event.index)
    if len(current) > 1:
        result.update(current)
    return result


def _header(events: list[Event]) -> Event:
    go: Event | None = None
    for event in events:
        if event.tag == "GO":
            if go is not None:
                reason = "inconsistent_events"
                raise event.error(reason, "unexpected GO")
            player_count(event)
            go = event
        elif go is None and event.tag not in METADATA:
            reason = "invalid_attribute"
            raise event.error(reason, "GO required before play", "GO")
    if go is None:
        reason = "invalid_attribute"
        raise ConversionError(reason, "GO required before play", field="GO")
    return go


def _start_round(
    state: RoundState | None, event: Event, count: int
) -> RoundState:
    if state is not None:
        if not state.finished:
            reason = "incomplete_log"
            raise event.error(reason, "previous round did not finish")
        state.check_settlement()
    return RoundState.start(event, count)


def convert_log(  # noqa: C901 -- chronological dispatch and completion checks
    xml: bytes, *, log_id: str
) -> list[ScoringCase]:
    """Convert completed rounds with positioned conversion errors."""
    if not log_id.strip():
        message = "log_id must not be empty"
        raise ValueError(message)

    events = parse_xml(xml)
    go = _header(events)
    multiple_ron = multiple_ron_indices(events)

    state: RoundState | None = None
    cases: list[ScoringCase] = []
    ids: set[str] = set()

    for event in events:
        if event.tag in METADATA or event.tag == "GO":
            continue
        if event.tag == "INIT":
            state = _start_round(state, event, player_count(go))
            continue
        if state is None:
            reason = "inconsistent_events"
            raise event.error(reason, "INIT required before play")
        if event.tag == "AGARI":
            case = extract(
                event,
                state,
                go,
                log_id,
                multiple_ron=event.index in multiple_ron,
            )
            if case["case_id"] in ids:
                reason = "inconsistent_events"
                raise event.error(reason, "duplicate case ID")
            ids.add(case["case_id"])
            cases.append(case)
            state.results.append(case["expected"])
            state.winners.add(event.integer("who"))
            state.finished = True
        elif state.finished:
            reason = "inconsistent_events"
            raise event.error(reason, "action after round ended")
        elif event.tag == "RYUUKYOKU":
            state.finish_draw(event)
        else:
            advance(state, event)

    if state is None or not state.finished:
        reason = "incomplete_log"
        raise ConversionError(reason, "log must end after a completed round")
    state.check_settlement()
    return cases


def advance(state: RoundState, event: Event) -> None:
    match = re.fullmatch(r"([T-WD-G])([0-9]+)", event.tag)
    if match:
        letter, value = match.groups()
        if letter in "TUVW":
            state.draw("TUVW".index(letter), int(value), event)
        else:
            state.discard("DEFG".index(letter), int(value), event)
    elif event.tag == "REACH":
        state.reach(event)
    elif event.tag == "N":
        state.call(event)
    elif event.tag == "DORA":
        state.dora(event)
    else:
        reason = "unknown_event"
        raise event.error(reason, f"unknown event {event.tag}")


def extract(
    event: Event,
    state: RoundState,
    go: Event,
    log_id: str,
    *,
    multiple_ron: bool = False,
) -> ScoringCase:
    if state.finished and not state.winners:
        reason = "inconsistent_events"
        raise event.error(reason, "win after drawn round")
    situation = state.situation(event)
    who = event.integer("who")
    source = event.integer("fromWho")
    seed = state.init.numbers("seed")
    wind = ("east", "south", "west", "north")[seed[0] // 4]
    number = seed[0] % 4 + 1
    ba = event.numbers("ba")
    if len(ba) != 2 or ba[0] != seed[1] or ba[1] < 0:
        reason = "inconsistent_events"
        raise event.error(reason, "invalid honba or sticks", "ba")
    if not state.winners and ba[1] != state.sticks:
        reason = "inconsistent_events"
        raise event.error(reason, "sticks differ from progression", "ba")
    winning = event.integer("machi")
    hand = event.numbers("hai")
    hand.remove(winning)
    players = player_count(go)
    expected, exclusions = expected_values(
        event, players, multiple_ron=multiple_ron
    )
    melds = (
        [decode_meld(code, who, event) for code in event.numbers("m")]
        if "m" in event.attributes
        else []
    )
    ura = (
        event.numbers("doraHaiUra") if "doraHaiUra" in event.attributes else []
    )
    for value in ura:
        state.check_tile(value, event)
    win_number = len(state.winners) + 1
    try:
        return parse_case(
            {
                "schema_version": "v1",
                "case_type": "scoring",
                "case_id": (
                    f"tenhou:{quote(log_id, safe='')}:{wind}:"
                    f"{number}:{seed[1]}:{win_number}"
                ),
                "source": {
                    "platform": "tenhou",
                    "log_id": log_id,
                    "event_index": event.index,
                    "winner_index": 0,
                    "scoring_values": {
                        **event.attributes,
                        "GO": go.attributes,
                    },
                },
                "ruleset": "tenhou-ranked-match",
                "player_count": players,
                "round": {
                    "wind": wind,
                    "number": number,
                    "honba": seed[1],
                    "riichi_sticks": state.sticks,
                    "dealer_seat": state.dealer,
                },
                "win_number": win_number,
                "input": {
                    "winner_seat": who,
                    "discarder_seat": None if who == source else source,
                    "concealed_tiles": [tile(value) for value in hand],
                    "winning_tile": tile(winning),
                    "melds": [
                        meld.corpus_value()
                        for meld in melds
                        if meld.kind != "nuki"
                    ],
                    "nuki_count": len(state.players[who].norths),
                    "dora_indicators": [
                        tile(value) for value in state.indicators
                    ],
                    "ura_dora_indicators": [tile(value) for value in ura],
                    "situation": situation,
                },
                "situation_provenance": {
                    "method": "event_reconstruction",
                    "event_indices": list(
                        range(state.init.index, event.index + 1)
                    ),
                    "unknown_fields": {},
                },
                "expected": expected,
                "comparison": {"excluded_fields": exclusions},
            }
        )
    except CorpusError as e:
        reason = "invalid_case"
        raise event.error(reason, e.message, e.field) from e
