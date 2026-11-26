import json
from typing import TYPE_CHECKING

import pytest
from corpus import read_dataset
from majsoul_converter import ConversionError
from majsoul_converter.cli import main
from majsoul_converter.conversion import convert_log
from majsoul_converter.datasets import convert_files
from majsoul_converter.liqi import liqi_pb2 as pb
from validator.validation import validate_case

if TYPE_CHECKING:
    from pathlib import Path

    from google.protobuf.message import Message


def wrap(message: Message) -> bytes:
    return pb.Wrapper(
        name=f".lq.{type(message).__name__}",
        data=message.SerializeToString(),
    ).SerializeToString()


def replay(*, actions: bool, uuid: str = "test-replay") -> bytes:
    hand = [
        "1z",
        "1z",
        "1z",
        "1m",
        "2m",
        "3m",
        "1p",
        "2p",
        "3p",
        "1s",
        "2s",
        "3s",
        "5p",
    ]
    events = [
        pb.RecordNewRound(scores=[25000] * 4, tiles0=[*hand, "9m"], dora="8s"),
        pb.RecordDiscardTile(seat=0, tile="9m"),
        pb.RecordDealTile(seat=1, tile="5p", left_tile_count=68),
        pb.RecordDiscardTile(seat=1, tile="5p"),
        pb.RecordHule(
            hules=[
                pb.HuleInfo(
                    seat=0,
                    qinjia=True,
                    hand=hand,
                    hu_tile="5p",
                    doras=["8s"],
                    fans=[
                        pb.FanInfo(id=10, val=1),
                        pb.FanInfo(id=11, val=1),
                        pb.FanInfo(id=17, val=2),
                        pb.FanInfo(id=33, val=0),
                    ],
                    count=4,
                    fu=40,
                    title_id=1,
                    point_rong=12000,
                )
            ],
            old_scores=[25000] * 4,
            delta_scores=[12000, -12000, 0, 0],
            scores=[37000, 13000, 25000, 25000],
        ),
    ]
    records = [wrap(event) for event in events]
    detail = (
        pb.GameDetailRecords(
            version=210715,
            actions=[
                pb.GameAction(),
                *(pb.GameAction(result=record) for record in records),
            ],
        )
        if actions
        else pb.GameDetailRecords(records=records)
    )
    return response_frame(detail, uuid=uuid)


def response_frame(
    detail: pb.GameDetailRecords, *, uuid: str = "test-replay"
) -> bytes:
    response = pb.ResGameRecord(
        head=pb.RecordGame(uuid=uuid, config=pb.GameConfig(category=2)),
        data=wrap(detail),
    )
    return (
        b"\x03\x00\x00"
        + pb.Wrapper(data=response.SerializeToString()).SerializeToString()
    )


@pytest.mark.parametrize("actions", [False, True])
def test_wind_yaku_and_dataset(tmp_path: Path, *, actions: bool) -> None:
    inputs = tmp_path / "logs"
    inputs.mkdir()
    source = inputs / "game.bin"
    source.write_bytes(replay(actions=actions))
    (inputs / "ignored.pb").write_bytes(b"")
    (inputs / "ignored.json").write_bytes(b"")
    dataset = tmp_path / "corpus"
    manifest = convert_files(inputs, dataset)
    assert manifest["record_count"] == 1
    [case] = convert_log(source.read_bytes())
    assert list(read_dataset(dataset)) == [case]
    assert case["source"]["log_id"] == "test-replay"
    assert case["expected"]["yaku"] == [
        {"id": "jikaze_ton", "han": 1, "yakuman_multiplier": 0},
        {"id": "bakaze_ton", "han": 1, "yakuman_multiplier": 0},
        {"id": "sanshoku_doujun", "han": 2, "yakuman_multiplier": 0},
    ]
    assert case["input"]["discarder_seat"] == 1
    assert validate_case(case)["status"] == "passed"


@pytest.mark.parametrize(
    ("fan_id", "multiplier", "title"),
    [(42, 1, "yakuman"), (49, 2, "double_yakuman")],
)
def test_kokushi_title_and_fu_exclusion(
    fan_id: int, multiplier: int, title: str
) -> None:
    hand = [
        "1m",
        "9m",
        "1p",
        "9p",
        "1s",
        "9s",
        "1z",
        "2z",
        "3z",
        "4z",
        "5z",
        "6z",
        "7z",
    ]
    if multiplier == 1:
        hand[0] = "9m"
    points = 32000 * multiplier
    events = [
        pb.RecordNewRound(
            scores=[25000] * 4, tiles0=["1m"], tiles1=hand, dora="2m"
        ),
        pb.RecordDiscardTile(seat=0, tile="1m"),
        pb.RecordHule(
            hules=[
                pb.HuleInfo(
                    seat=1,
                    hand=hand,
                    hu_tile="1m",
                    yiman=True,
                    count=multiplier,
                    title_id=4 + multiplier,
                    fans=[pb.FanInfo(id=fan_id, val=multiplier)],
                    fu=40,
                    point_rong=points,
                ),
            ],
            old_scores=[25000] * 4,
            delta_scores=[-points, points, 0, 0],
        ),
    ]
    data = response_frame(
        pb.GameDetailRecords(records=[wrap(event) for event in events])
    )
    [case] = convert_log(data, log_id="kokushi")
    assert case["expected"]["title"] == title
    assert case["expected"]["yakuman_multiplier"] == multiplier
    assert case["expected"]["fu"] == 40
    result = validate_case(case)
    assert result["fields"]["fu"]["status"] == "excluded"
    assert result["status"] == "passed"

    win_event = events[-1]
    assert isinstance(win_event, pb.RecordHule)
    win_event.hules[0].count = multiplier + 1
    data = response_frame(
        pb.GameDetailRecords(records=[wrap(event) for event in events])
    )
    with pytest.raises(ConversionError, match=r"expected\.yakuman_multiplier"):
        convert_log(data, log_id="kokushi")


def test_sanma_nuki_replacement_draw() -> None:
    hand = [
        "1z",
        "1z",
        "1z",
        "1p",
        "2p",
        "3p",
        "4p",
        "5p",
        "6p",
        "1s",
        "2s",
        "3s",
        "9s",
    ]
    events = [
        pb.RecordNewRound(
            scores=[35000] * 3,
            tiles0=["9m"],
            tiles1=[*hand[:-1], "4z"],
            dora="5z",
        ),
        pb.RecordDiscardTile(seat=0, tile="9m"),
        pb.RecordDealTile(seat=1, tile="9s", left_tile_count=53),
        pb.RecordBaBei(seat=1),
        pb.RecordDealTile(seat=1, tile="9s", left_tile_count=52),
        pb.RecordHule(
            hules=[
                pb.HuleInfo(
                    seat=1,
                    zimo=True,
                    hand=hand[::-1],
                    hu_tile="9s",
                    fans=[
                        pb.FanInfo(id=1, val=1),
                        pb.FanInfo(id=4, val=1),
                        pb.FanInfo(id=11, val=1),
                        pb.FanInfo(id=34, val=1),
                    ],
                    count=4,
                    fu=40,
                    title_id=1,
                    point_zimo_qin=4000,
                    point_zimo_xian=2000,
                ),
            ],
            old_scores=[35000] * 3,
            delta_scores=[-4000, 6000, -2000],
            scores=[31000, 41000, 33000],
        ),
    ]
    data = response_frame(
        pb.GameDetailRecords(records=[wrap(event) for event in events])
    )
    [case] = convert_log(data, log_id="sanma")
    assert case["player_count"] == 3
    assert case["source"]["scoring_values"]["old_scores"] == [35000] * 3
    assert case["source"]["scoring_values"]["scores"] == [31000, 41000, 33000]
    assert case["expected"]["event_score_deltas"] == [-4000, 6000, -2000]
    assert case["input"]["concealed_tiles"] == hand[::-1]
    assert case["input"]["winning_tile"] == "9s"
    assert case["input"]["nuki_count"] == 1
    assert case["input"]["situation"]["rinshan"]
    assert case["expected"]["payments_by_seat"] == [4000, 0, 2000]
    assert validate_case(case)["status"] == "passed"


def test_closed_kan_restores_red_five() -> None:
    hand = ["1m", "2m", "3m", "1s", "2s", "3s", "5z", "5z", "5z", "2p"]
    kan = ["0p", "5p", "5p", "5p"]
    events = [
        pb.RecordNewRound(scores=[25000] * 4, tiles0=hand + kan, dora="4m"),
        pb.RecordAnGangAddGang(seat=0, type=3, tiles="5p", doras=["4m", "8s"]),
        pb.RecordDealTile(seat=0, tile="2p", left_tile_count=68),
        pb.RecordHule(
            hules=[
                pb.HuleInfo(
                    seat=0,
                    qinjia=True,
                    zimo=True,
                    hand=hand,
                    hu_tile="2p",
                    fans=[
                        pb.FanInfo(id=1, val=1),
                        pb.FanInfo(id=4, val=1),
                        pb.FanInfo(id=7, val=1),
                        pb.FanInfo(id=32, val=1),
                    ],
                    count=4,
                    fu=50,
                    title_id=1,
                    point_zimo_xian=4000,
                ),
            ],
            old_scores=[25000] * 4,
            delta_scores=[12000, -4000, -4000, -4000],
        ),
    ]
    data = response_frame(
        pb.GameDetailRecords(records=[wrap(event) for event in events])
    )
    [case] = convert_log(data, log_id="ankan")
    assert case["input"]["melds"] == [
        {
            "type": "ankan",
            "tiles": kan,
            "called_tile_index": None,
            "from_seat": None,
        },
    ]
    assert case["input"]["dora_indicators"] == ["4m", "8s"]
    assert validate_case(case)["status"] == "passed"


@pytest.mark.parametrize("suffix", [".pb", ".json"])
def test_file_requires_bin_suffix(tmp_path: Path, suffix: str) -> None:
    source = tmp_path / f"game{suffix}"
    source.write_bytes(replay(actions=False))
    with pytest.raises(ConversionError, match=r"\.bin"):
        convert_files(source, tmp_path / "corpus")


@pytest.mark.parametrize("embedded", [False, True])
def test_rejects_payload_without_response_frame(*, embedded: bool) -> None:
    frame = replay(actions=False)
    serialized_response = pb.Wrapper.FromString(frame[3:]).data
    payload = (
        pb.ResGameRecord.FromString(serialized_response).data
        if embedded
        else serialized_response
    )

    with pytest.raises(ConversionError, match="response frame"):
        convert_log(payload)


@pytest.mark.parametrize(
    ("target", "case_type", "complete", "expected"),
    [
        ("agari-complete", "agari", True, {"is_agari": True}),
        ("agari-tenpai", "agari", False, {"is_agari": False}),
        ("shanten-agari", "shanten", True, {"shanten": -1}),
        ("shanten-tenpai", "shanten", False, {"shanten": 0}),
    ],
)
def test_shape_dataset(
    tmp_path: Path,
    target: str,
    case_type: str,
    expected: dict[str, bool | int],
    *,
    complete: bool,
) -> None:
    source = tmp_path / "game.bin"
    source.write_bytes(replay(actions=True))
    dataset = tmp_path / "corpus"
    assert (
        main([str(source), "--output", str(dataset), "--target", target]) == 0
    )

    [case] = read_dataset(dataset)
    assert case["case_type"] == case_type
    assert case["expected"] == expected
    assert case["source"]["log_id"] == "test-replay"
    assert case["input"]["concealed_tiles"].count("5p") == (
        2 if complete else 1
    )
    assert validate_case(case)["status"] == "passed"


@pytest.mark.parametrize("fourth_hand", [False, True])
def test_sanma_rejects_data_for_fourth_seat(*, fourth_hand: bool) -> None:
    start = pb.RecordNewRound(scores=[35000] * 3, dora="5z")
    if fourth_hand:
        start.tiles3.append("1z")
    events = [
        start,
        pb.RecordNoTile(),
    ]
    data = response_frame(
        pb.GameDetailRecords(records=[wrap(event) for event in events])
    )

    if fourth_hand:
        with pytest.raises(ConversionError, match="inactive seat"):
            convert_log(data)
    else:
        assert convert_log(data) == []


@pytest.mark.parametrize("valid", [True, False])
def test_cli_writes_conversion_report(tmp_path: Path, *, valid: bool) -> None:
    source = tmp_path / "game.bin"
    source.write_bytes(replay(actions=True) if valid else b"invalid")
    output = tmp_path / "corpus"
    report_path = tmp_path / "reports" / "conversion.json"

    status = main(
        [
            str(source),
            "--output",
            str(output),
            "--report",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert status == (0 if valid else 1)
    assert report["dataset_published"] is valid
    assert report["summary_complete"] is valid
    assert report["conversion"]["input_count"] == 1
    assert report["conversion"]["converted_count"] == (1 if valid else 0)
    assert report["record_count"] == (1 if valid else 0)
    assert output.is_dir() is valid
    if valid:
        assert report["error"] is None
        assert report["diagnostics"] == []
    else:
        assert report["conversion"]["failed_by_reason"] == {
            "conversion_error": 1
        }
        [diagnostic] = report["diagnostics"]
        assert diagnostic["path"] == str(source)
        assert "response frame" in diagnostic["message"]


def test_directory_uses_relative_path_order(tmp_path: Path) -> None:
    source = tmp_path / "logs"
    nested = source / "a"
    nested.mkdir(parents=True)
    (source / "z.bin").write_bytes(replay(actions=True, uuid="first-id"))
    (nested / "z.BIN").write_bytes(replay(actions=False, uuid="second-id"))
    output = tmp_path / "corpus"

    manifest = convert_files(source, output, cases_per_file=1)

    assert manifest["conversion"]["converted_count"] == 2
    assert [case["source"]["log_id"] for case in read_dataset(output)] == [
        "second-id",
        "first-id",
    ]
