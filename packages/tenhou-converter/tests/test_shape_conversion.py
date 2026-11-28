from pathlib import Path

import pytest
from corpus import read_dataset, read_manifest
from tenhou_converter import ConversionError, convert_log
from tenhou_converter.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_generates_shape_dataset(
    tmp_path: Path,
    shape_target: tuple[str, str, bool, dict[str, bool | int]],
) -> None:
    target, case_type, complete, expected = shape_target
    output = tmp_path / target
    assert (
        main(
            [
                "mjlog",
                str(FIXTURES / "four-ron.xml"),
                "--target",
                target,
                "--output",
                str(output),
            ]
        )
        == 0
    )

    (case,) = read_dataset(output)
    assert case["case_type"] == case_type
    assert case["expected"] == expected
    assert type(next(iter(case["expected"].values()))) is type(
        next(iter(expected.values()))
    )
    assert len(case["input"]["concealed_tiles"]) == (14 if complete else 13)
    manifest = read_manifest(output / "manifest.json")
    assert manifest["case_type"] == case_type
    assert manifest["generator"]["settings"]["target"] == target
    assert manifest["conversion"]["converted_count"] == 1
    assert manifest["record_count"] == 1


def test_ankan_is_retained_and_only_the_winning_east_is_removed() -> None:
    (case,) = convert_log(
        (FIXTURES / "synthetic-ankan-rinshan.xml").read_bytes(),
        log_id="kan:test",
        target="shanten-tenpai",
    )

    assert case["case_type"] == "shanten"
    assert case["case_id"] == "tenhou:kan%3Atest:6:shanten:tenpai"
    assert case["input"]["concealed_tiles"] == [
        "1m",
        "2m",
        "3m",
        "1p",
        "2p",
        "3p",
        "1s",
        "2s",
        "3s",
        "1z",
    ]
    (meld,) = case["input"]["melds"]
    assert meld["type"] == "ankan"
    assert len(meld["tiles"]) == 4


def test_sanma_keeps_red_tiles_and_excludes_north_extractions() -> None:
    (case,) = convert_log(
        (FIXTURES / "sanma-three-nuki.xml").read_bytes(),
        log_id="sanma",
        target="agari-complete",
    )

    assert case["player_count"] == 3
    assert case["input"]["melds"] == []
    assert len(case["input"]["concealed_tiles"]) == 14
    assert "4z" not in case["input"]["concealed_tiles"]
    assert "0p" in case["input"]["concealed_tiles"]


def test_double_ron_emits_one_case_per_win_in_event_order() -> None:
    xml = (FIXTURES / "synthetic-double-ron.xml").read_bytes()
    cases = convert_log(xml, log_id="double", target="shanten-agari")
    assert [case["case_id"] for case in cases] == [
        "tenhou:double:4:shanten:complete",
        "tenhou:double:5:shanten:complete",
    ]


def test_shape_conversion_does_not_require_scoring_expectations() -> None:
    xml = (
        (FIXTURES / "four-ron.xml")
        .read_bytes()
        .replace(b'yaku="1,1,2,1,53,0"', b'yaku="999,1"')
    )
    with pytest.raises(ConversionError, match="999"):
        convert_log(xml, log_id="unknown-yaku")

    (case,) = convert_log(xml, log_id="unknown-yaku", target="agari-complete")
    assert case["expected"] == {"is_agari": True}


def test_shape_conversion_checks_the_recorded_hand_against_play() -> None:
    xml = (
        (FIXTURES / "four-ron.xml")
        .read_bytes()
        .replace(
            b'hai="3,5,8,18,19,21,22,23,55,59,60,94,98,102"',
            b'hai="2,5,8,18,19,21,22,23,55,59,60,94,98,102"',
        )
    )
    with pytest.raises(ConversionError, match="differs from reconstructed"):
        convert_log(xml, log_id="bad-hai", target="agari-complete")


def test_draw_produces_no_shape_cases() -> None:
    xml = (FIXTURES / "sanma-ryuukyoku.xml").read_bytes()
    assert not convert_log(xml, log_id="draw", target="agari-tenpai")
