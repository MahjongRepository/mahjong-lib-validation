from typing import TYPE_CHECKING

from mahjong.hand_calculating.yaku_config import YakuConfig

if TYPE_CHECKING:
    from corpus.models import Yaku, YakuId

# Library attributes, not source-specific numeric IDs.
YAKU_NAMES: dict[str, YakuId] = {
    "tsumo": "menzen_tsumo",
    "riichi": "riichi",
    "ippatsu": "ippatsu",
    "chankan": "chankan",
    "rinshan": "rinshan",
    "haitei": "haitei",
    "houtei": "houtei",
    "pinfu": "pinfu",
    "tanyao": "tanyao",
    "iipeiko": "iipeikou",
    "seat_wind_east": "jikaze_ton",
    "seat_wind_south": "jikaze_nan",
    "seat_wind_west": "jikaze_sha",
    "seat_wind_north": "jikaze_pei",
    "round_wind_east": "bakaze_ton",
    "round_wind_south": "bakaze_nan",
    "round_wind_west": "bakaze_sha",
    "round_wind_north": "bakaze_pei",
    "haku": "yakuhai_haku",
    "hatsu": "yakuhai_hatsu",
    "chun": "yakuhai_chun",
    "daburu_riichi": "double_riichi",
    "chiitoitsu": "chiitoitsu",
    "chantai": "chanta",
    "ittsu": "ittsuu",
    "sanshoku": "sanshoku_doujun",
    "sanshoku_douko": "sanshoku_doukou",
    "sankantsu": "sankantsu",
    "toitoi": "toitoi",
    "sanankou": "sanankou",
    "shosangen": "shousangen",
    "honroto": "honroutou",
    "ryanpeiko": "ryanpeikou",
    "junchan": "junchan",
    "honitsu": "honitsu",
    "chinitsu": "chinitsu",
    "renhou": "renhou",
    "tenhou": "tenhou",
    "chiihou": "chiihou",
    "daisangen": "daisangen",
    "suuankou": "suuankou",
    "suuankou_tanki": "suuankou_tanki",
    "tsuisou": "tsuuiisou",
    "ryuisou": "ryuuiisou",
    "chinroto": "chinroutou",
    "chuuren_poutou": "chuuren_poutou",
    "daburu_chuuren_poutou": "junsei_chuuren_poutou",
    "kokushi": "kokushi_musou",
    "daburu_kokushi": "kokushi_musou_13men",
    "daisuushi": "daisuushii",
    "shosuushi": "shousuushii",
    "suukantsu": "suukantsu",
    "dora": "dora",
    "ura_dora": "ura_dora",
    "aka_dora": "aka_dora",
}
_config = YakuConfig()
YAKU_IDS: dict[int, YakuId] = {
    getattr(_config, name).yaku_id: key for name, key in YAKU_NAMES.items()
}


def comparable_yaku(yaku: list[Yaku]) -> dict[str, tuple[int | None, int]]:
    result: dict[str, tuple[int | None, int]] = {
        item["id"]: (item["han"], item["yakuman_multiplier"])
        for item in yaku
        if item["id"] not in {"dora", "nuki_dora"}
    }
    # The library includes nuki in Dora and cannot verify the split.
    dora = sum(
        item["han"] or 0
        for item in yaku
        if item["id"] in {"dora", "nuki_dora"}
    )
    if dora:
        result["dora"] = (dora, 0)
    return result
