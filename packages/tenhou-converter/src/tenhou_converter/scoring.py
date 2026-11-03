# Numeric constants below describe the mjlog wire layout.
# ruff: noqa: PLR2004
from corpus.models import ExcludedField, Expected, Title, Yaku, YakuId

from tenhou_converter.parser import Event

# Source IDs are positional and independent of the corpus Literal order.
YAKU_IDS: tuple[YakuId, ...] = (
    "menzen_tsumo",
    "riichi",
    "ippatsu",
    "chankan",
    "rinshan",
    "haitei",
    "houtei",
    "pinfu",
    "tanyao",
    "iipeikou",
    "jikaze_ton",
    "jikaze_nan",
    "jikaze_sha",
    "jikaze_pei",
    "bakaze_ton",
    "bakaze_nan",
    "bakaze_sha",
    "bakaze_pei",
    "yakuhai_haku",
    "yakuhai_hatsu",
    "yakuhai_chun",
    "double_riichi",
    "chiitoitsu",
    "chanta",
    "ittsuu",
    "sanshoku_doujun",
    "sanshoku_doukou",
    "sankantsu",
    "toitoi",
    "sanankou",
    "shousangen",
    "honroutou",
    "ryanpeikou",
    "junchan",
    "honitsu",
    "chinitsu",
    "renhou",
    "tenhou",
    "chiihou",
    "daisangen",
    "suuankou",
    "suuankou_tanki",
    "tsuuiisou",
    "ryuuiisou",
    "chinroutou",
    "chuuren_poutou",
    "junsei_chuuren_poutou",
    "kokushi_musou",
    "kokushi_musou_13men",
    "daisuushii",
    "shousuushii",
    "suukantsu",
    "dora",
    "ura_dora",
    "aka_dora",
)
TITLES: tuple[Title, ...] = (
    "below_mangan",
    "mangan",
    "haneman",
    "baiman",
    "sanbaiman",
    "yakuman",
)


def yaku_values(event: Event) -> list[Yaku]:
    yakuman = "yakuman" in event.attributes
    field = "yakuman" if yakuman else "yaku"
    values = event.numbers(field)
    pairs: list[tuple[int, int | None]]
    if yakuman:
        if "yaku" in event.attributes:
            msg = "invalid_attribute"
            raise event.error(msg, "invalid yaku representation", field)
        pairs = [(key, None) for key in values]
    else:
        if len(values) % 2:
            msg = "invalid_attribute"
            raise event.error(msg, "invalid yaku representation", field)
        pairs = list(zip(values[::2], values[1::2], strict=True))

    result: list[Yaku] = []
    seen: set[int] = set()
    for key, han in pairs:
        if not 0 <= key < len(YAKU_IDS):
            msg = "unknown_yaku_id"
            raise event.error(msg, f"unknown yaku {key}", field)
        if key in seen or yakuman != (37 <= key <= 51):
            msg = "invalid_attribute"
            raise event.error(msg, "duplicate or misclassified yaku", field)
        seen.add(key)
        if han == 0 and key == 53:
            continue
        if han is not None and han <= 0:
            msg = "invalid_attribute"
            raise event.error(msg, "han must be positive", field)
        result.append(
            {
                "id": YAKU_IDS[key],
                "han": han,
                "yakuman_multiplier": 1 if yakuman else 0,
            }
        )
    return result


def _score_title(event: Event, rank: int, multiplier: int, han: int) -> Title:
    title = TITLES[rank]
    if multiplier and title != "yakuman":
        msg = "invalid_attribute"
        raise event.error(msg, "yakuman conflicts with title", "ten")
    if title == "yakuman" and not multiplier:
        if han < 13:
            msg = "invalid_attribute"
            raise event.error(
                msg, "kazoe needs at least thirteen recorded han", "yaku"
            )
        return "kazoe_yakuman"
    return title


def expected_values(
    event: Event, players: int, *, multiple_ron: bool = False
) -> tuple[Expected, list[ExcludedField]]:
    yaku = yaku_values(event)
    ten = event.numbers("ten")
    sc = event.numbers("sc")
    if len(ten) != 3 or not 0 <= ten[2] < len(TITLES) or min(ten) < 0:
        msg = "invalid_attribute"
        raise event.error(msg, "invalid score tuple", "ten")
    if len(sc) != 8 or (players == 3 and sc[6:] != [0, 0]):
        msg = "invalid_attribute"
        raise event.error(msg, "invalid seat score pairs", "sc")
    who = event.integer("who")
    deltas = [value * 100 for value in sc[1 : players * 2 : 2]]
    multiplier = sum(value["yakuman_multiplier"] for value in yaku)
    han = sum(value["han"] or 0 for value in yaku)
    title = _score_title(event, ten[2], multiplier, han)

    payments = [-min(value, 0) for value in deltas]
    total_paid = sum(payments)
    gain = deltas[who]
    honba = total_paid - ten[1]
    sticks = gain - total_paid
    other_gains = any(
        value > 0 for seat, value in enumerate(deltas) if seat != who
    )
    shared = multiple_ron and other_gains
    # Shared deltas describe several wins, so individual gains cannot be
    # reconciled with the total paid by all payers.
    invalid_individual_allocation = not shared and (sticks < 0 or other_gains)
    if honba < 0 or payments[who] or invalid_individual_allocation:
        msg = "inconsistent_events"
        raise event.error(
            msg,
            "score deltas cannot describe this win",
            "sc",
        )

    exclusions: list[ExcludedField] = []
    if any(
        value["id"] in ("kokushi_musou", "kokushi_musou_13men")
        for value in yaku
    ):
        exclusions.append(
            {"field": "fu", "reason": "kokushi_fu_not_comparable"}
        )
    if "paoWho" in event.attributes:
        pao = event.integer("paoWho")
        if not 0 <= pao < players or pao == who:
            msg = "invalid_attribute"
            raise event.error(msg, "invalid liable seat", "paoWho")
        exclusions.append(
            {"field": "payments_by_seat", "reason": "liability_payment"}
        )
    result: Expected = {
        "title": title,
        "yaku": yaku,
        "han": None if multiplier else han,
        "fu": ten[0],
        "yakuman_multiplier": multiplier,
        "base_points": ten[1],
        "honba_points": honba,
        "riichi_stick_points": sticks,
        "winner_gain": gain,
        "payments_by_seat": payments,
        "event_score_deltas": deltas,
    }
    if shared:
        result["honba_points"] = None
        result["riichi_stick_points"] = None
        result["payments_by_seat"] = None
        excluded_fields = {item["field"] for item in exclusions}
        for field in (
            "honba_points",
            "riichi_stick_points",
            "payments_by_seat",
        ):
            if field in excluded_fields:
                continue
            exclusions.append(
                {"field": field, "reason": "multiple_ron_allocation_unknown"}
            )
    return result, exclusions
