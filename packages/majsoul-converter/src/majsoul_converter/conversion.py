from typing import TYPE_CHECKING, Literal, get_args, overload
from urllib.parse import quote

from corpus import Case, ScoringCase, parse_case, parse_scoring_case

from majsoul_converter.decoder import ConversionError, decode
from majsoul_converter.liqi import liqi_pb2 as pb
from majsoul_converter.reconstruction import RoundState
from majsoul_converter.scoring import expected_values

if TYPE_CHECKING:
    from collections.abc import Sequence


_WINDS = ("east", "south", "west", "north")

ShapeTarget = Literal[
    "agari-complete",
    "agari-tenpai",
    "shanten-tenpai",
    "shanten-agari",
]
Target = Literal["scoring", ShapeTarget]
TARGETS = get_args(Target)


@overload
def convert_log(
    payload: bytes,
    *,
    log_id: str | None = None,
    fallback_id: str | None = None,
    target: Literal["scoring"] = "scoring",
) -> list[ScoringCase]: ...


@overload
def convert_log(
    payload: bytes,
    *,
    log_id: str | None = None,
    fallback_id: str | None = None,
    target: Target,
) -> Sequence[Case]: ...


def convert_log(  # noqa: C901 -- validates the sequence of round boundaries
    payload: bytes,
    *,
    log_id: str | None = None,
    fallback_id: str | None = None,
    target: Target = "scoring",
) -> Sequence[Case]:
    if target not in TARGETS:
        msg = f"unknown conversion target {target!r}"
        raise ConversionError(msg)

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
            if state is None:
                if not isinstance(event, pb.RecordNewRound):
                    msg = "expected a new round"
                    raise ConversionError(msg)
                state = RoundState(event, index)
                continue

            if isinstance(event, (pb.RecordNoTile, pb.RecordLiuJu)):
                state = None
                continue

            if isinstance(event, pb.RecordHule):
                wins = _win_cases(event, state, identifier, index, target)
                for case in wins:
                    if case["case_id"] in ids:
                        msg = "duplicate case ID"
                        raise ConversionError(msg)
                    ids.add(case["case_id"])
                    cases.append(case)
                state = None
                continue

            state.advance(event)
            state.event_indices.append(index)
        except (ValueError, IndexError, KeyError) as e:
            msg = f"event {index} ({type(event).__name__}): {e}"
            raise ConversionError(msg, event_index=index) from e

    if not events or state is not None:
        msg = "replay must end with a completed round"
        raise ConversionError(msg)
    return cases


def _win_cases(
    event: pb.RecordHule,
    state: RoundState,
    log_id: str,
    index: int,
    target: Target,
) -> list[Case]:
    if not event.hules or len({win.seat for win in event.hules}) != len(
        event.hules
    ):
        msg = "win event must contain distinct winners"
        raise ConversionError(msg)
    start = state.start
    wind = _WINDS[start.chang]
    number = start.ju + 1
    source = {"platform": "majsoul", "log_id": log_id, "event_index": index}
    cases: list[Case] = []
    for winner_index, win in enumerate(event.hules):
        hand, payer = state.win_input(win, event)
        win_number = winner_index + 1
        case_id = (
            f"majsoul:{quote(log_id, safe='')}:"
            f"{wind}:{number}:{start.ben}:{win_number}"
        )

        if target != "scoring":
            complete = target in ("agari-complete", "shanten-agari")
            tiles = [*win.hand, win.hu_tile] if complete else list(win.hand)
            case_type = "agari" if target.startswith("agari-") else "shanten"
            cases.append(
                parse_case(
                    {
                        "schema_version": "v1",
                        "case_type": case_type,
                        "case_id": f"{case_id}:{target}",
                        "source": source,
                        "player_count": state.count,
                        "input": {
                            "concealed_tiles": tiles,
                            "melds": hand["melds"],
                        },
                        "expected": (
                            {"is_agari": complete}
                            if case_type == "agari"
                            else {"shanten": -1 if complete else 0}
                        ),
                    }
                )
            )
            continue

        expected, exclusions = expected_values(win, event, state, payer)
        case = parse_scoring_case(
            {
                "schema_version": "v1",
                "case_type": "scoring",
                "case_id": case_id,
                "source": {
                    **source,
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
