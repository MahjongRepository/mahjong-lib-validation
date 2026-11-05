from typing import Any

import pytest
from corpus import CorpusError, parse_case


@pytest.mark.parametrize("name", ["riichi", "dora", "daisangen"])
@pytest.mark.parametrize("excluded", [False, True])
def test_duplicate_yaku_id_is_rejected(
    example: dict[str, Any], name: str, *, excluded: bool
) -> None:
    yakuman = name == "daisangen"
    example["expected"].update(
        yaku=[
            {
                "id": name,
                "han": None if yakuman else value,
                "yakuman_multiplier": value if yakuman else 0,
            }
            for value in (1, 2)
        ],
        han=None if yakuman else 3,
        yakuman_multiplier=3 if yakuman else 0,
    )
    if excluded:
        example["comparison"]["excluded_fields"] = [
            {"field": "yaku", "reason": "not compared"},
            {"field": "han", "reason": "not compared"},
        ]

    with pytest.raises(CorpusError) as error:
        parse_case(example)

    assert error.value.field == "expected.yaku[1].id"
    assert "duplicate" in str(error.value)


@pytest.mark.parametrize(
    "name", ["unknown_yaku", "", "riichi ", "daburu_riichi", "ittsu"]
)
def test_undefined_yaku_name_is_rejected(
    example: dict[str, Any], name: str
) -> None:
    example["expected"]["yaku"][0]["id"] = name

    with pytest.raises(CorpusError) as error:
        parse_case(example)

    assert error.value.field == "expected.yaku[0].id"


@pytest.mark.parametrize(
    "name",
    [
        "jikaze_ton",
        "bakaze_sha",
        "yakuhai_chun",
        "double_riichi",
        "chiitoitsu",
        "ittsuu",
        "ura_dora",
        "nuki_dora",
        "renhou",
    ],
)
def test_common_yaku_names_are_preserved(
    example: dict[str, Any], name: str
) -> None:
    example["expected"]["yaku"][0]["id"] = name

    yaku = parse_case(example)["expected"]["yaku"]
    assert yaku is not None
    assert yaku[0]["id"] == name


@pytest.mark.parametrize(
    "name",
    [
        "suuankou_tanki",
        "kokushi_musou_13men",
        "junsei_chuuren_poutou",
        "daisuushii",
    ],
)
def test_special_yakuman_forms_keep_their_own_names(
    example: dict[str, Any], name: str
) -> None:
    example["expected"].update(
        {
            "title": "yakuman",
            "han": None,
            "yakuman_multiplier": 1,
            "yaku": [{"id": name, "han": None, "yakuman_multiplier": 1}],
        }
    )

    case = parse_case(example)

    yaku = case["expected"]["yaku"]
    assert yaku is not None
    assert yaku[0]["id"] == name
    assert case["expected"]["yakuman_multiplier"] == 1
