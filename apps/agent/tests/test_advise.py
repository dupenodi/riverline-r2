"""Advice bullets follow the ledger; payoff is the engine's last word."""

from datetime import date

from advise import advice_payload, draft_points, picture, short_date
from cashflow import Entry, project

TODAY = date(2026, 9, 14)


def _e(id: str, kind: str, label: str, **kwargs) -> Entry:
    return Entry(id=id, kind=kind, label=label, **kwargs)  # type: ignore[arg-type]


def test_draft_covers_daily_burn_and_same_day_lumps() -> None:
    entries = [
        _e("z", "need", "Zomato", amount=600, cadence="daily"),
        _e("r", "need", "Rapido", amount=250, cadence="daily"),
        _e("s1", "debt", "Motilal SIP", amount=5000, day=15),
        _e("s2", "debt", "HDFC SIP", amount=3000, day=15),
        _e("d", "flex", "Dinner", amount=3000, day=27, cadence="once"),
        _e("f", "income", "Freelance", amount=18000, day=25, cadence="once"),
    ]
    proj = project(TODAY, 40_000, entries)
    brief = picture(TODAY, 40_000, entries, proj)
    points = draft_points(brief)
    blob = " ".join(points)
    assert "Zomato" in blob
    assert "Rapido" in blob
    assert "SIP" in blob
    assert "Dinner" in blob
    payload = advice_payload(TODAY, 40_000, entries, proj)
    assert payload["payoff"]["ok"] is True
    assert payload["payoff"]["date"] == proj.crunch.date.isoformat()
    assert payload["points"]
    assert "stays above zero" not in blob.lower()


def test_short_date() -> None:
    assert short_date("2026-09-18") == "18 Sep"
