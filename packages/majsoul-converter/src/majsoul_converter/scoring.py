"""Translate win records into the shared scoring expectations."""

from typing import TYPE_CHECKING

from majsoul_converter.decoder import ConversionError

if TYPE_CHECKING:
    from corpus.models import ExcludedField, Expected, Title, Yaku, YakuId

    from majsoul_converter.liqi import liqi_pb2 as pb
    from majsoul_converter.reconstruction import RoundState

_URA_DORA = 33

TITLES: tuple[Title, ...] = (
    "below_mangan",
    "mangan",
    "haneman",
    "baiman",
    "sanbaiman",
    "yakuman",
    "double_yakuman",
    "triple_yakuman",
    "quadruple_yakuman",
    "quintuple_yakuman",
    "sextuple_yakuman",
    "kazoe_yakuman",
)
YAKU_IDS: dict[int, YakuId] = {
    1: "menzen_tsumo",
    2: "riichi",
    3: "chankan",
    4: "rinshan",
    5: "haitei",
    6: "houtei",
    7: "yakuhai_haku",
    8: "yakuhai_hatsu",
    9: "yakuhai_chun",
    12: "tanyao",
    13: "iipeikou",
    14: "pinfu",
    15: "chanta",
    16: "ittsuu",
    17: "sanshoku_doujun",
    18: "double_riichi",
    19: "sanshoku_doukou",
    20: "sankantsu",
    21: "toitoi",
    22: "sanankou",
    23: "shousangen",
    24: "honroutou",
    25: "chiitoitsu",
    26: "junchan",
    27: "honitsu",
    28: "ryanpeikou",
    29: "chinitsu",
    30: "ippatsu",
    31: "dora",
    32: "aka_dora",
    _URA_DORA: "ura_dora",
    34: "nuki_dora",
    35: "tenhou",
    36: "chiihou",
    37: "daisangen",
    38: "suuankou",
    39: "tsuuiisou",
    40: "ryuuiisou",
    41: "chinroutou",
    42: "kokushi_musou",
    43: "shousuushii",
    44: "suukantsu",
    45: "chuuren_poutou",
    47: "junsei_chuuren_poutou",
    48: "suuankou_tanki",
    49: "kokushi_musou_13men",
    50: "daisuushii",
}
_SEAT_WIND = 10
_ROUND_WIND = 11
_SEAT_YAKU: tuple[YakuId, ...] = (
    "jikaze_ton",
    "jikaze_nan",
    "jikaze_sha",
    "jikaze_pei",
)
_ROUND_YAKU: tuple[YakuId, ...] = (
    "bakaze_ton",
    "bakaze_nan",
    "bakaze_sha",
    "bakaze_pei",
)


def _yaku(win: pb.HuleInfo, state: RoundState) -> list[Yaku]:
    seat_wind = (win.seat - state.start.ju) % state.count
    ids = YAKU_IDS | {
        _SEAT_WIND: _SEAT_YAKU[seat_wind],
        _ROUND_WIND: _ROUND_YAKU[state.start.chang],
    }
    return [
        {
            "id": ids[fan.id],
            "han": None if win.yiman else fan.val,
            "yakuman_multiplier": fan.val if win.yiman else 0,
        }
        for fan in win.fans
        if fan.id != _URA_DORA or fan.val != 0
    ]


def expected_values(
    win: pb.HuleInfo,
    event: pb.RecordHule,
    state: RoundState,
    payer: int | None,
) -> tuple[Expected, list[ExcludedField]]:
    count = state.count
    dealer = state.start.ju
    yaku = _yaku(win, state)
    base_payments = [0] * count
    if payer is None:
        for seat in range(count):
            if seat != win.seat:
                base_payments[seat] = (
                    win.point_zimo_qin
                    if seat == dealer
                    else win.point_zimo_xian
                )
    else:
        base_payments[payer] = win.point_rong
    base = sum(base_payments)

    delta = list(event.delta_scores)
    if len(delta) != count or len(event.old_scores) != count:
        msg = (
            "win record must have score deltas and old scores for every player"
        )
        raise ConversionError(msg)
    if event.scores and list(event.scores) != [
        old + change
        for old, change in zip(event.old_scores, delta, strict=True)
    ]:
        msg = "win score deltas do not match final scores"
        raise ConversionError(msg)

    gain = delta[win.seat]
    nearest = (
        win.seat
        if payer is None
        else min(
            (hule.seat for hule in event.hules),
            key=lambda seat: (seat - payer) % count,
        )
    )
    sticks = state.sticks * 1000 if win.seat == nearest else 0
    honba = gain - base - sticks
    exclusions: list[ExcludedField] = []
    payments: list[int] | None = base_payments
    if event.baopai > 0 or win.baopai or win.baopai_seats:
        payments = None
        exclusions.append({"field": "payments_by_seat", "reason": "pao"})
    elif payer is None:
        payments = [
            -change if seat != win.seat else 0
            for seat, change in enumerate(delta)
        ]
    else:
        payments[payer] += honba

    if any(
        value["id"] in ("kokushi_musou", "kokushi_musou_13men")
        for value in yaku
    ):
        exclusions.append(
            {"field": "fu", "reason": "kokushi_fu_not_comparable"}
        )
    elif not win.fu:
        exclusions.append({"field": "fu", "reason": "fu_not_recorded"})

    return {
        "title": TITLES[win.title_id],
        "yaku": yaku,
        "han": None if win.yiman else win.count,
        "fu": win.fu or None,
        "yakuman_multiplier": win.count if win.yiman else 0,
        "base_points": base,
        "honba_points": honba,
        "riichi_stick_points": sticks,
        "winner_gain": gain,
        "payments_by_seat": payments,
        "event_score_deltas": delta,
    }, exclusions
