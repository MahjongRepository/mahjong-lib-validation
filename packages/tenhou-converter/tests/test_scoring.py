from tenhou_converter.parser import Event
from tenhou_converter.scoring import expected_values


def test_kazoe_is_regular_han_and_keeps_recorded_fu() -> None:
    record = Event(
        15,
        "AGARI",
        {
            "who": "0",
            "ten": "20,48000,5",
            "yaku": "35,6,1,1,2,1,0,1,7,1,9,1,54,1,52,1",
            "sc": "250,480,250,-160,250,-160,250,-160",
        },
    )
    expected, exclusions = expected_values(record, 4)
    assert expected["title"] == "kazoe_yakuman"
    assert expected["han"] == 13
    assert expected["yakuman_multiplier"] == 0
    assert expected["fu"] == 20
    assert exclusions == []


def test_liability_payments_are_preserved_but_not_compared() -> None:
    record = Event(
        16,
        "AGARI",
        {
            "who": "1",
            "ten": "70,32000,5",
            "yakuman": "39",
            "paoWho": "2",
            "sc": "250,-160,250,343,250,-163,250,0",
        },
    )
    expected, exclusions = expected_values(record, 4)
    assert expected["payments_by_seat"] == [16000, 0, 16300, 0]
    assert expected["honba_points"] == 300
    assert expected["riichi_stick_points"] == 2000
    assert exclusions == [
        {"field": "payments_by_seat", "reason": "liability_payment"}
    ]


def test_composite_yakuman_uses_each_recorded_single_multiplier() -> None:
    record = Event(
        17,
        "AGARI",
        {
            "who": "1",
            "ten": "70,64000,5",
            "yakuman": "39,42",
            "sc": "250,-640,250,640,250,0,250,0",
        },
    )
    expected, exclusions = expected_values(record, 4)
    assert expected["yakuman_multiplier"] == 2
    assert expected["han"] is None
    assert expected["fu"] == 70
    assert exclusions == []
