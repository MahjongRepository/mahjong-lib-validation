import pytest
from tenhou_converter.errors import ConversionError, UnsupportedLogError
from tenhou_converter.parser import Event
from tenhou_converter.rules import player_count


@pytest.mark.parametrize(
    "attributes",
    [
        {"type": "40", "lobby": "0"},
        *(
            {"type": str(41 | flag), "lobby": "0"}
            for flag in (0x002, 0x004, 0x100, 0x200, 0x400, 0x800)
        ),
        {"type": "41", "lobby": "1"},
        {"type": "40"},
        {"type": "43", "lobby": "invalid"},
    ],
)
def test_unsupported_rules_preserve_exclusion_details_and_check_order(
    attributes: dict[str, str],
) -> None:
    with pytest.raises(UnsupportedLogError) as caught:
        player_count(Event(9, "GO", attributes))

    assert caught.value.reason == "unsupported_rules"
    assert caught.value.field == "type"
    assert caught.value.event_index == 9


@pytest.mark.parametrize("game_type", ["40", "43", "41"])
def test_unknown_type_bits_are_checked_before_rule_exclusions(
    game_type: str,
) -> None:
    with pytest.raises(ConversionError) as caught:
        player_count(Event(9, "GO", {"type": str(int(game_type) | 0x1000)}))

    assert not isinstance(caught.value, UnsupportedLogError)
    assert caught.value.reason == "invalid_attribute"
    assert caught.value.field == "type"
    assert caught.value.event_index == 9


@pytest.mark.parametrize("game_type", [41, 185])
def test_supported_type_still_requires_valid_lobby(game_type: int) -> None:
    with pytest.raises(ConversionError) as caught:
        player_count(
            Event(9, "GO", {"type": str(game_type), "lobby": "invalid"})
        )

    assert not isinstance(caught.value, UnsupportedLogError)
    assert caught.value.reason == "invalid_attribute"
    assert caught.value.field == "lobby"
    assert caught.value.event_index == 9


@pytest.mark.parametrize(("game_type", "expected"), [(41, 4), (185, 3)])
def test_supported_ranked_rules_return_player_count(
    game_type: int, expected: int
) -> None:
    assert (
        player_count(Event(9, "GO", {"type": str(game_type), "lobby": "0"}))
        == expected
    )
