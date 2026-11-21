from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tenhou_converter.parser import Event


def check_shared_payments(
    events: list[Event], players: int, *, honba: int, sticks: int
) -> None:
    """Check group totals without choosing individual bonus recipients.

    A liable winner can pay another winner. Their net loss does not give
    the gross payment, so only bounds can be checked in that case.
    """
    deltas = [value * 100 for value in events[0].numbers("sc")[1::2]][:players]
    bases = {event.integer("who"): event.numbers("ten")[1] for event in events}
    liable = {
        event.integer("paoWho")
        for event in events
        if "paoWho" in event.attributes
    }
    bonus = honba + sticks
    for winner, base in bases.items():
        if deltas[winner] > base + bonus or (
            winner not in liable and deltas[winner] < base
        ):
            reason = "inconsistent_events"
            raise events[0].error(
                reason,
                "shared winner income conflicts with base points and bonuses",
                "sc",
            )

    cancelled = (
        sum(bases.values()) + bonus - sum(deltas[seat] for seat in bases)
    )
    # Payments disappear from net totals only when the payer also wins.
    # Bound them by the recorded wins for which that winner is liable;
    # do not invent the liable yakuman's share in a composite hand.
    maximum_cancelled = sum(
        event.numbers("ten")[1]
        for event in events
        if "paoWho" in event.attributes and event.integer("paoWho") in bases
    )
    if maximum_cancelled:
        maximum_cancelled += honba
    if not 0 <= cancelled <= maximum_cancelled:
        reason = "inconsistent_events"
        raise events[0].error(
            reason, "shared payments conflict with base points and honba", "sc"
        )


def check_win_balances(
    events: list[Event], starting: list[int], *, shared_scores: bool
) -> list[int]:
    """Check balances in wire units, counting shared deltas once."""
    balances = starting.copy()
    for event in events:
        scores = event.numbers("sc")
        if scores[::2] != (starting if shared_scores else balances):
            reason = "inconsistent_events"
            raise event.error(
                reason, "win starting balance conflicts with progression", "sc"
            )
        balances = [
            before + delta
            for before, delta in zip(scores[::2], scores[1::2], strict=True)
        ]
    return balances
