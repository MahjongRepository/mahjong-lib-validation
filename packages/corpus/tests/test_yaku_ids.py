from typing import Any

import pytest
from corpus import CorpusError, parse_case


@pytest.mark.parametrize("name", ["unknown_yaku", "", "riichi "])
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
        "daburu_riichi",
        "chiitoitsu",
        "ura_dora",
        "nuki_dora",
        "renhou",
    ],
)
def test_common_yaku_names_are_preserved(
    example: dict[str, Any], name: str
) -> None:
    example["expected"]["yaku"][0]["id"] = name

    assert parse_case(example)["expected"]["yaku"][0]["id"] == name


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

    assert case["expected"]["yaku"][0]["id"] == name
    assert case["expected"]["yakuman_multiplier"] == 1
