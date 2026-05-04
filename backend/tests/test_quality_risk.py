"""Tests for Wave 1: trademark shield, quality gates, prompt templates,
warmup scheduler, fingerprint isolation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# ─────── Trademark Shield ───────


def test_trademark_blacklist_blocks_known_brands():
    from app.services.trademark import check_phrase

    assert not check_phrase("Mickey Mouse Birthday Tee").safe
    assert not check_phrase("Star Wars day shirt").safe
    assert not check_phrase("Pokemon trainer mug").safe
    assert not check_phrase("NFL fan club hoodie").safe


def test_trademark_blacklist_substring_markers():
    from app.services.trademark import check_phrase

    res = check_phrase("Coffee Lovers ™ Premium")
    assert not res.safe
    assert "™" in res.reason or res.matched_phrase == "™"


def test_trademark_safe_passes_through():
    from app.services.trademark import check_phrase

    safe_phrases = [
        "vintage mountain hiking lover",
        "cozy autumn vibes",
        "botanical mushroom field guide",
    ]
    for p in safe_phrases:
        assert check_phrase(p).safe, f"expected safe: {p!r}"


def test_trademark_user_blacklist():
    from app.services.trademark import check_phrase

    res = check_phrase(
        "support team alpha forever",
        user_blacklist=["team alpha"],
    )
    assert not res.safe
    assert res.source == "user_blacklist"
    assert res.matched_phrase == "team alpha"


def test_trademark_filter_keywords():
    from app.services.trademark import filter_keywords

    safe, rejected = filter_keywords(
        ["vintage cat lover", "Disney princess tee", "cozy autumn hiking"]
    )
    assert "vintage cat lover" in safe
    assert "cozy autumn hiking" in safe
    assert any("Disney" in r[0] for r in rejected)


def test_trademark_word_boundary():
    """'nike' should NOT match 'nikename' (word boundary check)."""
    from app.services.trademark import check_phrase

    assert check_phrase("interesting moniker shirt").safe
    assert not check_phrase("nike runner club tee").safe


# ─────── Quality Gates ───────


def test_quality_evaluate_design_handles_missing_deps(tmp_path):
    """If cv2/pytesseract aren't installed, gates return 'untested', never crash."""
    # Create a tiny dummy PNG
    from PIL import Image

    from app.services.quality import evaluate_design

    p = tmp_path / "tiny.png"
    Image.new("RGBA", (16, 16), (200, 100, 50, 255)).save(p)

    report = evaluate_design(str(p), expected_keyword="cat")
    # Either rejected (deps installed) or all gates untested (deps missing) — never crash.
    assert isinstance(report.gates, list)
    assert len(report.gates) >= 3
    for gate in report.gates:
        assert gate.status in ("pass", "fail", "untested")


def test_quality_report_serializes():
    from app.services.quality import GateResult, QualityReport

    rpt = QualityReport(
        gates=[GateResult(name="sharpness", status="pass", score=0.9)],
        overall_score=0.9,
    )
    d = rpt.to_dict()
    assert d["overall_score"] == 0.9
    assert d["gates"][0]["name"] == "sharpness"


# ─────── Prompt Templates ───────


def test_prompt_templates_complete():
    from app.services.prompt_templates import TEMPLATES, families, list_all

    assert len(TEMPLATES) == 20  # exactly 20 art-school templates
    fams = families()
    assert {"cinematic", "vintage", "cultural", "botanical", "brutalist"} == set(fams)
    # Each family has at least 2 templates
    for fam in fams:
        assert sum(1 for t in TEMPLATES if t.family == fam) >= 2

    # Unique ids
    ids = [t.id for t in TEMPLATES]
    assert len(set(ids)) == len(ids)

    # Listing serialization shape
    serialized = list_all()
    assert all({"id", "name", "family", "preview"} <= set(s.keys()) for s in serialized)


def test_prompt_templates_render_substitutes():
    from app.services.prompt_templates import render

    out = render("vintage_bauhaus", niche="cat lovers", keyword="grumpy cat")
    # Substitution worked
    assert "cat lovers" in out
    assert "grumpy cat" in out
    # POD safety suffix appended
    assert "transparent background" in out
    assert "no watermark" in out


def test_prompt_templates_unknown_id_raises():
    from app.services.prompt_templates import render

    with pytest.raises(KeyError):
        render("does_not_exist", niche="x", keyword="y")


# ─────── Warm-up Scheduler ───────


def test_warmup_tier_thresholds():
    from app.services.warmup import tier_for_age

    assert tier_for_age(0).daily_cap == 3
    assert tier_for_age(5).daily_cap == 3
    assert tier_for_age(10).daily_cap == 5
    assert tier_for_age(20).daily_cap == 8
    assert tier_for_age(40).daily_cap == 12
    assert tier_for_age(100).daily_cap == 18


def test_warmup_user_override_cap():
    from app.services.warmup import daily_cap

    # User override beats tier
    assert daily_cap(created_at=None, override_days=0, user_override_cap=25) == 25


def test_warmup_decide_publish_blocks_when_capped():
    from app.services.warmup import decide_publish

    decision = decide_publish(
        created_at=datetime.now(UTC),
        override_age_days=0,
        user_override_cap=None,
        today_published=3,  # at week 1 cap
        last_publish_at=None,
    )
    assert not decision.allowed
    assert "cap" in decision.reason.lower()


def test_warmup_decide_publish_blocks_on_spacing():
    from app.services.warmup import decide_publish

    decision = decide_publish(
        created_at=datetime.now(UTC),
        override_age_days=0,
        user_override_cap=None,
        today_published=0,
        last_publish_at=datetime.now(UTC) - timedelta(seconds=5),
        min_spacing_seconds=30,
    )
    assert not decision.allowed
    assert "spacing" in decision.reason.lower()


def test_warmup_decide_publish_allows_normal_case():
    from app.services.warmup import decide_publish

    decision = decide_publish(
        created_at=datetime.now(UTC) - timedelta(days=20),
        override_age_days=None,
        user_override_cap=None,
        today_published=0,
        last_publish_at=None,
    )
    assert decision.allowed
    assert decision.cap == 8  # weeks_3_4


# ─────── Fingerprint Isolation ───────


def test_fingerprint_deterministic_per_account():
    from app.services.fingerprint import fingerprint_for_account

    fp_a1 = fingerprint_for_account(1)
    fp_a1_again = fingerprint_for_account(1)
    fp_a2 = fingerprint_for_account(2)

    assert fp_a1.user_agent == fp_a1_again.user_agent
    assert fp_a1.accept_language == fp_a1_again.accept_language
    # Different accounts likely get different UA (not guaranteed but very probable for 1 vs 2)
    # At minimum the fp_a2 is also stable
    assert fingerprint_for_account(2).user_agent == fp_a2.user_agent


def test_fingerprint_proxy_passthrough():
    from app.services.fingerprint import fingerprint_for_account

    fp = fingerprint_for_account(5, proxy_url="http://user:pass@proxy.example:8080")
    assert fp.proxy_url == "http://user:pass@proxy.example:8080"


def test_fingerprint_account_gate_serializes():
    """Two acquires for the same account must serialize."""
    import threading

    from app.services.fingerprint import account_gate

    gate = account_gate()
    order: list[str] = []

    def worker(name: str) -> None:
        release = gate.acquire(99, min_spacing_s=0.0)
        order.append(f"start_{name}")
        # do nothing
        order.append(f"end_{name}")
        release()

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Each "start" must be immediately followed by its matching "end"
    for i in range(0, len(order), 2):
        assert order[i].startswith("start_")
        assert order[i + 1] == order[i].replace("start_", "end_")
