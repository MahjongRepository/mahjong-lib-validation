from typing import TYPE_CHECKING

from mahjong.hand_calculating.yaku_config import YakuConfig

if TYPE_CHECKING:
    from corpus.models import Yaku, YakuId

_config = YakuConfig()
YAKU_NAMES: dict[str, YakuId] = {
    _config.tsumo.name: "menzen_tsumo",
    _config.riichi.name: "riichi",
    _config.ippatsu.name: "ippatsu",
    _config.chankan.name: "chankan",
    _config.rinshan.name: "rinshan",
    _config.haitei.name: "haitei",
    _config.houtei.name: "houtei",
    _config.pinfu.name: "pinfu",
    _config.tanyao.name: "tanyao",
    _config.iipeiko.name: "iipeikou",
    _config.seat_wind_east.name: "jikaze_ton",
    _config.seat_wind_south.name: "jikaze_nan",
    _config.seat_wind_west.name: "jikaze_sha",
    _config.seat_wind_north.name: "jikaze_pei",
    _config.round_wind_east.name: "bakaze_ton",
    _config.round_wind_south.name: "bakaze_nan",
    _config.round_wind_west.name: "bakaze_sha",
    _config.round_wind_north.name: "bakaze_pei",
    _config.haku.name: "yakuhai_haku",
    _config.hatsu.name: "yakuhai_hatsu",
    _config.chun.name: "yakuhai_chun",
    _config.daburu_riichi.name: "double_riichi",
    _config.chiitoitsu.name: "chiitoitsu",
    _config.chantai.name: "chanta",
    _config.ittsu.name: "ittsuu",
    _config.sanshoku.name: "sanshoku_doujun",
    _config.sanshoku_douko.name: "sanshoku_doukou",
    _config.sankantsu.name: "sankantsu",
    _config.toitoi.name: "toitoi",
    _config.sanankou.name: "sanankou",
    _config.shosangen.name: "shousangen",
    _config.honroto.name: "honroutou",
    _config.ryanpeiko.name: "ryanpeikou",
    _config.junchan.name: "junchan",
    _config.honitsu.name: "honitsu",
    _config.chinitsu.name: "chinitsu",
    _config.renhou.name: "renhou",
    _config.tenhou.name: "tenhou",
    _config.chiihou.name: "chiihou",
    _config.daisangen.name: "daisangen",
    _config.suuankou.name: "suuankou",
    _config.suuankou_tanki.name: "suuankou_tanki",
    _config.tsuisou.name: "tsuuiisou",
    _config.ryuisou.name: "ryuuiisou",
    _config.chinroto.name: "chinroutou",
    _config.chuuren_poutou.name: "chuuren_poutou",
    _config.daburu_chuuren_poutou.name: "junsei_chuuren_poutou",
    _config.kokushi.name: "kokushi_musou",
    _config.daburu_kokushi.name: "kokushi_musou_13men",
    _config.daisuushi.name: "daisuushii",
    _config.shosuushi.name: "shousuushii",
    _config.suukantsu.name: "suukantsu",
    _config.dora.name: "dora",
    _config.ura_dora.name: "ura_dora",
    _config.aka_dora.name: "aka_dora",
}
YAKU_IDS: dict[int, YakuId] = {
    yaku.yaku_id: YAKU_NAMES[yaku.name]
    for yaku in vars(_config).values()
    if yaku.name in YAKU_NAMES
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
