from urllib.parse import quote

from corpus import ScoringCase, parse_scoring_case

from majsoul_converter.decoder import ConversionError, decode
from majsoul_converter.liqi import liqi_pb2 as pb
from majsoul_converter.reconstruction import RoundState
from majsoul_converter.scoring import expected_values

_WINDS = ("east", "south", "west", "north")


def convert_log(  # noqa: C901 -- validates the sequence of round boundaries
    payload: bytes,
    *,
    log_id: str | None = None,
    fallback_id: str | None = None,
) -> list[ScoringCase]:
    recorded_id, events = decode(payload)
    identifier = (recorded_id or fallback_id) if log_id is None else log_id
    if not identifier or not identifier.strip():
        msg = "log ID required when the replay has no UUID"
        raise ConversionError(msg)
    state: RoundState | None = None
    cases = []
    ids: set[str] = set()
    for index, event in events:
        try:
            if isinstance(event, pb.RecordNewRound) and state is None:
                state = RoundState(event, index)
            elif state is None:
                msg = "expected a new round"
                raise ConversionError(msg)
            elif isinstance(event, (pb.RecordNoTile, pb.RecordLiuJu)):
                state = None
            elif isinstance(event, pb.RecordHule):
                for case in _win_cases(event, state, identifier, index):
                    if case["case_id"] in ids:
                        msg = "duplicate case ID"
                        raise ConversionError(msg)
                    ids.add(case["case_id"])
                    cases.append(case)
                state = None
            else:
                state.advance(event)
                state.event_indices.append(index)
        except (ValueError, IndexError, KeyError) as e:
            msg = f"event {index} ({type(event).__name__}): {e}"
            raise ConversionError(msg) from e
    if not events or state is not None:
        msg = "replay must end with a completed round"
        raise ConversionError(msg)
    return cases


def _win_cases(
    event: pb.RecordHule, state: RoundState, log_id: str, index: int
) -> list[ScoringCase]:
    if not event.hules or len({win.seat for win in event.hules}) != len(
        event.hules
    ):
        msg = "win event must contain distinct winners"
        raise ConversionError(msg)
    start = state.start
    wind = _WINDS[start.chang]
    number = start.ju + 1
    cases = []
    for winner_index, win in enumerate(event.hules):
        hand, payer = state.win_input(win, event)
        expected, exclusions = expected_values(win, event, state, payer)
        win_number = winner_index + 1
        case = parse_scoring_case(
            {
                "schema_version": "v1",
                "case_type": "scoring",
                "case_id": (
                    f"majsoul:{quote(log_id, safe='')}:"
                    f"{wind}:{number}:{start.ben}:{win_number}"
                ),
                "source": {
                    "platform": "majsoul",
                    "log_id": log_id,
                    "event_index": index,
                    "winner_index": winner_index,
                    "scoring_values": {
                        "title_id": win.title_id,
                        "point_rong": win.point_rong,
                        "point_sum": win.point_sum,
                        "point_zimo_qin": win.point_zimo_qin,
                        "point_zimo_xian": win.point_zimo_xian,
                        "old_scores": list(event.old_scores),
                        "delta_scores": list(event.delta_scores),
                        "scores": list(event.scores),
                    },
                },
                "ruleset": "majsoul-ranked-match",
                "player_count": state.count,
                "round": {
                    "wind": wind,
                    "number": number,
                    "honba": start.ben,
                    "riichi_sticks": state.sticks,
                    "dealer_seat": start.ju,
                },
                "win_number": win_number,
                "input": hand,
                "situation_provenance": {
                    "method": "event_reconstruction",
                    "event_indices": [*state.event_indices, index],
                    "unknown_fields": {},
                },
                "expected": expected,
                "comparison": {"excluded_fields": exclusions},
            }
        )
        cases.append(case)
    return cases
