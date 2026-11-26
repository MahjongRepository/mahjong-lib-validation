from typing import TYPE_CHECKING

import pytest
from corpus import read_dataset
from majsoul_converter import ConversionError
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


def replay(*, actions: bool) -> bytes:
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
    response = pb.ResGameRecord(
        head=pb.RecordGame(
            uuid="test-replay", config=pb.GameConfig(category=2)
        ),
        data=wrap(detail),
    )
    return (
        b"\x03\x00\x00"
        + pb.Wrapper(data=response.SerializeToString()).SerializeToString()
    )


@pytest.mark.parametrize("actions", [False, True])
def test_wind_yaku_and_dataset(tmp_path: Path, *, actions: bool) -> None:
    source = tmp_path / "game.bin"
    source.write_bytes(replay(actions=actions))
    dataset = tmp_path / "corpus"
    manifest = convert_files(source, dataset)
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
    data = wrap(
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
    data = wrap(
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
                    hand=hand,
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
        ),
    ]
    detail = wrap(
        pb.GameDetailRecords(records=[wrap(event) for event in events])
    )
    response = pb.ResGameRecord(
        head=pb.RecordGame(uuid="sanma"),
        data=detail,
    )
    [case] = convert_log(response.SerializeToString())
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
    data = wrap(
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
