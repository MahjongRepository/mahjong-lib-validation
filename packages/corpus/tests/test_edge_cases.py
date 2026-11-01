import json
from pathlib import Path
from typing import Any

import pytest
from corpus import (
    CorpusError,
    check_dataset,
    parse_case,
    read_cases,
    read_dataset,
    write_cases,
    write_dataset,
)

EDGE_FIXTURES = (
    "synthetic-sanma-tsumo.json",
    "synthetic-ankan.json",
    "synthetic-kakan.json",
    "majsoul-double-ron-first.json",
    "majsoul-double-ron-second.json",
    "synthetic-liability.json",
    "tenhou-kokushi.json",
    "synthetic-yakuman-ippatsu.json",
)


def _fixture(name: str) -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_unknown_situation_reason_is_preserved(
    example: dict[str, Any],
) -> None:
    example["input"]["situation"]["ippatsu"] = None
    example["situation_provenance"]["unknown_fields"] = {
        "ippatsu": "missing_events"
    }

    case = parse_case(example)

    assert case["situation_provenance"]["unknown_fields"] == {
        "ippatsu": "missing_events"
    }


@pytest.mark.parametrize(
    ("value", "reasons", "field"),
    [
        (None, {}, "ippatsu"),
        (None, {"ippatsu": " "}, "ippatsu"),
        (False, {"ippatsu": "missing_events"}, "ippatsu"),
        (False, {"not_a_flag": "missing_events"}, "not_a_flag"),
    ],
)
def test_unknown_reasons_match_only_unknown_situation_fields(
    example: dict[str, Any],
    reasons: dict[str, str],
    field: str,
    *,
    value: bool | None,
) -> None:
    example["input"]["situation"]["ippatsu"] = value
    example["situation_provenance"]["unknown_fields"] = reasons
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "situation_provenance.unknown_fields." + field


@pytest.mark.parametrize(
    ("kind", "called", "source", "field"),
    [
        ("ankan", 0, None, "called_tile_index"),
        ("ankan", None, 1, "from_seat"),
        ("kakan", None, 1, "called_tile_index"),
        ("kakan", 2, None, "from_seat"),
        ("kakan", 2, 2, "from_seat"),
        ("chii", None, 1, "called_tile_index"),
        ("pon", 2, None, "from_seat"),
        ("daiminkan", 2, None, "from_seat"),
    ],
)
def test_meld_origin_matches_open_or_closed_kind(
    example: dict[str, Any],
    kind: str,
    called: int | None,
    source: int | None,
    field: str,
) -> None:
    example["input"]["concealed_tiles"] = example["input"]["concealed_tiles"][
        3:
    ]
    tiles = (
        ["1m", "2m", "3m"]
        if kind == "chii"
        else ["1m"] * (3 if kind == "pon" else 4)
    )
    example["input"]["melds"] = [
        {
            "type": kind,
            "tiles": tiles,
            "called_tile_index": called,
            "from_seat": source,
        }
    ]
    with pytest.raises(CorpusError) as error:
        parse_case(example)
    assert error.value.field == "input.melds[0]." + field


def test_sanma_tsumo_and_nuki_fixture() -> None:
    case = parse_case(_fixture("synthetic-sanma-tsumo.json"))
    assert case["player_count"] == 3
    assert case["input"]["situation"]["tsumo"] is True
    assert case["input"]["nuki_count"] == 2
    assert case["expected"]["fu"] == 20
    assert case["expected"]["payments_by_seat"] == [4000, 0, 2000]
    assert case["expected"]["event_score_deltas"] == [-4000, 6000, -2000]


def test_ankan_and_kakan_fixture_metadata() -> None:
    ankan = parse_case(_fixture("synthetic-ankan.json"))
    kakan = parse_case(_fixture("synthetic-kakan.json"))
    assert ankan["input"]["melds"][0] == {
        "type": "ankan",
        "tiles": ["5z"] * 4,
        "called_tile_index": None,
        "from_seat": None,
    }
    assert kakan["input"]["melds"][0] == {
        "type": "kakan",
        "tiles": ["5z"] * 4,
        "called_tile_index": 2,
        "from_seat": 1,
    }
    assert ankan["expected"]["fu"] == 70
    assert kakan["expected"]["fu"] == 40


def test_actual_double_ron_keeps_each_gain_and_shared_event_delta() -> None:
    first = parse_case(_fixture("majsoul-double-ron-first.json"))
    second = parse_case(_fixture("majsoul-double-ron-second.json"))
    assert [first["win_number"], second["win_number"]] == [1, 2]
    assert [
        first["source"]["winner_index"],
        second["source"]["winner_index"],
    ] == [0, 1]
    assert (
        first["source"]["event_index"]
        == second["source"]["event_index"]
        == 577
    )
    assert first["expected"]["winner_gain"] == 3900
    assert second["expected"]["winner_gain"] == 12000
    assert first["expected"]["payments_by_seat"] == [0, 2900, 0, 0]
    assert second["expected"]["payments_by_seat"] == [0, 12000, 0, 0]
    assert (
        first["expected"]["event_score_deltas"]
        == second["expected"]["event_score_deltas"]
        == [12000, -14900, 0, 3900]
    )
    assert first["input"]["melds"][0]["tiles"] == ["2s", "3s", "4s"]


def test_liability_payments_are_preserved_but_excluded() -> None:
    case = parse_case(_fixture("synthetic-liability.json"))
    assert case["source"]["scoring_values"]["paoWho"] == 2
    assert case["expected"]["payments_by_seat"] == [16000, 0, 16300, 0]
    assert {
        "field": "payments_by_seat",
        "reason": "liability_payment",
    } in case["comparison"]["excluded_fields"]


def test_actual_kokushi_fu_and_counterfactual_ippatsu() -> None:
    recorded = parse_case(_fixture("tenhou-kokushi.json"))
    ippatsu = parse_case(_fixture("synthetic-yakuman-ippatsu.json"))
    assert recorded["expected"]["fu"] == 0
    assert {"field": "fu", "reason": "kokushi_fu_not_comparable"} in recorded[
        "comparison"
    ]["excluded_fields"]
    assert ippatsu["input"]["situation"]["ippatsu"] is True
    assert ippatsu["expected"]["yaku"] == [
        {"id": "kokushi_musou", "han": None, "yakuman_multiplier": 1}
    ]


@pytest.mark.parametrize("compress", [False, True])
def test_edge_fixtures_survive_manifest_dataset(
    tmp_path: Path, *, compress: bool
) -> None:
    values = [_fixture(name) for name in EDGE_FIXTURES]
    cases = [parse_case(value) for value in values]
    path = tmp_path / "dataset"
    manifest = write_dataset(
        path,
        iter(cases),
        cases_per_file=3,
        compress=compress,
        generator={
            "name": "corpus-fixtures",
            "version": "1",
            "settings": {"purpose": "schema-regression"},
        },
        conversion={
            "input_count": 7,
            "converted_count": 7,
            "failed_by_reason": {},
            "excluded_by_reason": {},
        },
    )
    assert [entry["record_count"] for entry in manifest["files"]] == [3, 3, 2]
    assert check_dataset(path)["record_count"] == 8
    assert list(read_dataset(path)) == values


def test_chankan_records_the_provider_in_discarder_seat(
    example: dict[str, Any],
) -> None:
    example["input"]["situation"]["chankan"] = True
    example["input"]["discarder_seat"] = 1
    case = parse_case(example)
    assert case["input"]["situation"]["tsumo"] is False
    assert case["input"]["situation"]["chankan"] is True
    assert case["input"]["discarder_seat"] == 1


@pytest.mark.parametrize("suffix", [".jsonl", ".jsonl.gz"])
def test_unknown_reason_survives_jsonl(
    tmp_path: Path, example: dict[str, Any], suffix: str
) -> None:
    example["input"]["situation"]["ippatsu"] = None
    example["situation_provenance"]["unknown_fields"] = {
        "ippatsu": "missing_events"
    }
    path = tmp_path / ("unknown" + suffix)
    write_cases(path, [parse_case(example)])
    values = list(read_cases(path))
    assert values[0]["input"]["situation"]["ippatsu"] is None
    assert (
        values[0]["situation_provenance"]["unknown_fields"]["ippatsu"]
        == "missing_events"
    )
