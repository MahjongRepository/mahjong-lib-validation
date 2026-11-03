import pytest
from tenhou_converter import ConversionError
from tenhou_converter.parser import Event
from tenhou_converter.scoring import expected_values, yaku_values


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


@pytest.mark.parametrize(
    ("attributes", "field", "message"),
    [
        (
            {"yakuman": "39", "yaku": "1,1"},
            "yakuman",
            "invalid yaku representation",
        ),
        ({"yakuman": "x", "yaku": "1,1"}, "yakuman", "expected integer list"),
        ({"yaku": "1,1,2"}, "yaku", "invalid yaku representation"),
    ],
)
def test_invalid_yaku_representation_preserves_error_details(
    attributes: dict[str, str], field: str, message: str
) -> None:
    with pytest.raises(ConversionError) as caught:
        yaku_values(Event(18, "AGARI", attributes))

    assert caught.value.reason == "invalid_attribute"
    assert caught.value.message == message
    assert caught.value.event_index == 18
    assert caught.value.field == field


def test_shared_ron_keeps_liability_exclusion_without_duplicates() -> None:
    record = Event(
        19,
        "AGARI",
        {
            "who": "1",
            "ten": "30,1300,0",
            "yaku": "1,1",
            "paoWho": "2",
            "sc": "250,-29,250,26,250,13,250,0",
        },
    )
    expected, exclusions = expected_values(record, 4, multiple_ron=True)

    assert expected["honba_points"] is None
    assert expected["riichi_stick_points"] is None
    assert expected["payments_by_seat"] is None
    assert exclusions == [
        {"field": "payments_by_seat", "reason": "liability_payment"},
        {"field": "honba_points", "reason": "multiple_ron_allocation_unknown"},
        {
            "field": "riichi_stick_points",
            "reason": "multiple_ron_allocation_unknown",
        },
    ]


@pytest.mark.parametrize(
    ("sc", "multiple_ron"),
    [
        ("250,-29,250,26,250,13,250,0", False),
        ("250,-10,250,26,250,13,250,0", True),
        ("250,26,250,-29,250,13,250,0", True),
    ],
)
def test_inconsistent_payments_are_not_hidden_by_shared_ron(
    sc: str, *, multiple_ron: bool
) -> None:
    record = Event(
        20,
        "AGARI",
        {"who": "1", "ten": "30,1300,0", "yaku": "1,1", "sc": sc},
    )
    with pytest.raises(ConversionError) as caught:
        expected_values(record, 4, multiple_ron=multiple_ron)

    assert caught.value.reason == "inconsistent_events"
    assert caught.value.message == "score deltas cannot describe this win"
    assert caught.value.event_index == 20
    assert caught.value.field == "sc"
