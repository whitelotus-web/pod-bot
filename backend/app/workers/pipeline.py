"""End-to-end pipeline: keyword → AI design → bg removal → mockup → SEO → publish.

Auto failover: image / seo keys rotate via app.services.ai_router when a
provider returns 429 / quota errors. Per-design failures are isolated; a single
broken design doesn't kill the entire campaign run.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from slugify import slugify

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import (
    Campaign,
    Design,
    Keyword,
    Mockup,
    PlatformAccount,
    Product,
    RunLog,
    TrademarkTerm,
)
from app.services.ai_router import safe_generate_image
from app.services.bg_remove import remove_background
from app.services.catalog import get_blueprint
from app.services.keywords import KeywordAggregator
from app.services.mockup import PillowMockup
from app.services.notifications import dispatch as notify
from app.services.platforms import get_platform
from app.services.quality import evaluate_design
from app.services.seo import generate_seo
from app.services.trademark import filter_keywords
from app.services.upscale import upscale as upscale_design
from app.services.warmup import decide_publish
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.pipeline.run_campaign")
def run_campaign(self, campaign_id: int, force_auto: bool | None = None) -> dict:
    """End-to-end run for a single campaign."""
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return {"ok": False, "error": "campaign_not_found"}

        run = RunLog(campaign_id=campaign_id, stage="pipeline", status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

        try:
            auto_mode = (
                "full" if force_auto else ("semi" if force_auto is False else campaign.auto_mode)
            )

            kw_log = _log(db, campaign_id, "keywords", "running")
            terms = _fetch_keywords(db, campaign)
            if campaign.trademark_check_enabled:
                terms = _trademark_filter(db, campaign, terms)
            kw_log.status = "success"
            kw_log.finished_at = datetime.now(UTC)
            kw_log.data = {"count": len(terms)}
            db.commit()

            design_log = _log(db, campaign_id, "design", "running")
            created_designs: list[Design] = []
            top_terms = terms[: max(1, campaign.designs_per_keyword)]
            for kw in top_terms:
                try:
                    designs = _generate_designs(db, campaign, kw)
                    for d in designs:
                        _ensure_transparent(db, d)
                        if campaign.quality_gates_enabled and not _quality_gate(db, campaign, d):
                            continue
                        if getattr(campaign, "upscale_enabled", True):
                            _upscale_design(db, campaign, d)
                        _render_mockups(db, d, campaign.product_types or ["tshirt_unisex"])
                        created_designs.append(d)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("design generation failed for %s: %s", kw.term, exc)
            design_log.status = "success"
            design_log.finished_at = datetime.now(UTC)
            design_log.data = {"count": len(created_designs)}
            db.commit()

            if auto_mode == "full":
                pub_log = _log(db, campaign_id, "publish", "running")
                published = _publish_all(db, campaign, created_designs)
                pub_log.status = "success"
                pub_log.finished_at = datetime.now(UTC)
                pub_log.data = {"published": published}
                db.commit()

            campaign.last_run_at = datetime.now(UTC)
            run.status = "success"
            run.finished_at = datetime.now(UTC)
            run.data = {
                "keywords": len(terms),
                "designs": len(created_designs),
                "auto_mode": auto_mode,
            }
            db.commit()
            return {"ok": True, "data": run.data}
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.message = str(exc)
            db.commit()
            logger.exception("Pipeline run failed")
            return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def _log(db, campaign_id: int, stage: str, status: str) -> RunLog:
    row = RunLog(campaign_id=campaign_id, stage=stage, status=status)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _trademark_filter(db, campaign: Campaign, terms: list[Keyword]) -> list[Keyword]:
    """Drop trademarked terms; mark them in DB and notify."""
    user_terms = [
        t.term
        for t in db.query(TrademarkTerm).filter(TrademarkTerm.user_id == campaign.user_id).all()
    ]
    safe_strings, rejected = filter_keywords(
        [t.term for t in terms],
        user_blacklist=user_terms,
        enable_uspto=campaign.uspto_check_enabled,
    )
    safe_set = set(safe_strings)
    kept: list[Keyword] = []
    for kw in terms:
        if kw.term in safe_set:
            kept.append(kw)
        else:
            reason = next((r for k, r in rejected if k == kw.term), "trademark")
            kw.rejected_reason = reason[:512]
            try:
                notify(
                    db,
                    user_id=campaign.user_id,
                    kind="trademark_hit",
                    payload={"phrase": kw.term, "reason": reason},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("notify trademark_hit failed: %s", exc)
    db.commit()
    return kept


def _upscale_design(db, campaign: Campaign, design: Design) -> None:
    """Upscale a design to print-ready DPI. Output stored as upscaled_path."""
    rel = design.bg_removed_path or design.file_path
    src = Path(settings.media_root) / rel
    if not src.exists():
        return
    target = max(2048, int(getattr(campaign, "upscale_min_long_edge", 4500) or 4500))
    out = src.with_name(src.stem + "_print.png")
    try:
        res = upscale_design(src, out_path=out, min_long_edge=target)
        design.upscaled_path = str(Path(res.output_path).relative_to(settings.media_root))
        design.upscale_backend = res.backend
        design.print_width = res.width
        design.print_height = res.height
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("upscale failed for design #%s: %s", design.id, exc)


def _quality_gate(db, campaign: Campaign, design: Design) -> bool:
    """Run design-time quality gates. Returns True if design passes."""
    rel = design.bg_removed_path or design.file_path
    abs_path = Path(settings.media_root) / rel
    if not abs_path.exists():
        return True
    keyword = design.keyword.term if design.keyword else design.title
    report = evaluate_design(str(abs_path), expected_keyword=keyword)
    design.quality_score = report.overall_score
    design.quality_report = report.to_dict()
    if report.rejected:
        design.status = "rejected"
        design.rejection_reason = report.rejection_reason
        db.commit()
        return False
    db.commit()
    return True


def _fetch_keywords(db, campaign: Campaign) -> list[Keyword]:
    sources = campaign.keyword_sources or ["google_trends"]
    agg = KeywordAggregator(source_names=sources)
    terms = agg.run(campaign.niche or campaign.name, top=campaign.designs_per_keyword * 4)

    saved: list[Keyword] = []
    for rank, t in enumerate(terms, start=1):
        kw = Keyword(
            campaign_id=campaign.id,
            term=t.term,
            source=t.source,
            score=t.score,
            rank=rank,
            raw=t.raw,
        )
        db.add(kw)
        saved.append(kw)
    db.commit()
    for k in saved:
        db.refresh(k)
    return saved


def _generate_designs(db, campaign: Campaign, keyword: Keyword) -> list[Design]:
    out: list[Design] = []
    Path(settings.media_root, "designs").mkdir(parents=True, exist_ok=True)
    # Use a throwaway engine instance just to compose the prompt the same way.
    from app.services.ai import get_engine

    base_prompt = get_engine(campaign.ai_engine).design_prompt(
        keyword.term, niche=campaign.niche, style=campaign.style_prompt
    )
    for i in range(max(1, campaign.designs_per_keyword)):
        prompt = base_prompt + f" Variation {i + 1}."
        try:
            img = safe_generate_image(
                db,
                user_id=campaign.user_id,
                engine_pref=campaign.ai_engine,
                prompt=prompt,
                model=campaign.ai_model,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI generate failed (all keys exhausted): %s", exc)
            continue
        fname = f"{campaign.id}_{keyword.id}_{i}_{slugify(keyword.term)[:40]}.png"
        fpath = Path(settings.media_root, "designs", fname)
        fpath.write_bytes(img.image_bytes)
        design = Design(
            campaign_id=campaign.id,
            keyword_id=keyword.id,
            title=keyword.term.title(),
            prompt=prompt,
            engine=campaign.ai_engine,
            model=img.model,
            file_path=str(fpath.relative_to(settings.media_root)),
            status="ready",
        )
        db.add(design)
        out.append(design)
    db.commit()
    for d in out:
        db.refresh(d)
    return out


def _ensure_transparent(db, design: Design) -> None:
    """If the engine cannot guarantee transparency, run rembg / threshold."""
    if design.engine == "gemini":
        return
    try:
        src = Path(settings.media_root) / design.file_path
        out = remove_background(src, src.with_name(src.stem + "_nobg.png"))
        design.bg_removed_path = str(out.relative_to(settings.media_root))
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("bg removal failed for design #%s: %s", design.id, exc)


def _render_mockups(db, design: Design, product_types: list[str]) -> None:
    mocker = PillowMockup()
    src_rel = design.bg_removed_path or design.file_path
    design_abs = Path(settings.media_root) / src_rel
    for ptype in product_types:
        # Map the catalog id to the Pillow template file.
        template = {
            "tshirt_unisex": "tshirt_white",
            "hoodie": "hoodie_gray",
            "sweatshirt": "tshirt_white",  # share template until we ship more PNGs
            "tank_top": "tshirt_white",
            "kids_tshirt": "tshirt_white",
            "mug_11oz": "tshirt_white",
            "tote_bag": "tshirt_white",
            "phone_case": "tshirt_white",
            "poster": "tshirt_white",
            "sticker": "tshirt_white",
        }.get(ptype, "tshirt_white")
        try:
            out_path = mocker.render(str(design_abs), template=template)
            rel = Path(out_path).relative_to(settings.media_root)
            db.add(
                Mockup(
                    design_id=design.id,
                    product_type=ptype,
                    template=template,
                    file_path=str(rel),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mockup render failed: %s", exc)
    db.commit()


def _select_accounts(db, campaign: Campaign, platform_name: str) -> list[PlatformAccount]:
    """Resolve the campaign's target shops for a platform.

    Filters out accounts that are unhealthy (``paused``/``banned``) or whose
    ``paused_until`` is still in the future, so the pipeline never publishes
    to a shop already flagged at risk by the health monitor — publishing to a
    paused/banned shop can escalate a warning into a permanent ban.

    Empty ``target_account_ids`` → first eligible account for the platform.
    Non-empty ``target_account_ids`` with no match for this platform → falls
    back to the first eligible account so the user doesn't experience a
    silent skip when they selected the platform but none of the chosen
    account ids belonged to it.
    """
    now = datetime.now(UTC)
    base_q = db.query(PlatformAccount).filter(
        PlatformAccount.user_id == campaign.user_id,
        PlatformAccount.platform == platform_name,
        PlatformAccount.is_active.is_(True),
        PlatformAccount.health_status.in_(("healthy", "warn")),
        (PlatformAccount.paused_until.is_(None)) | (PlatformAccount.paused_until <= now),
    )
    selected_ids = list(campaign.target_account_ids or [])
    if selected_ids:
        rows = base_q.filter(PlatformAccount.id.in_(selected_ids)).all()
        if rows:
            return rows
        # Intersection empty for this platform — fall back to first eligible
        # account so the user doesn't silently lose this platform.
        logger.warning(
            "target_account_ids %s contains no eligible %s account; "
            "falling back to first active+healthy account for the platform",
            selected_ids,
            platform_name,
        )
    first = base_q.order_by(PlatformAccount.id.asc()).first()
    return [first] if first else []


def _publish_all(db, campaign: Campaign, designs: list[Design]) -> int:
    published = 0
    targets = campaign.target_platforms or []
    product_types = campaign.product_types or ["tshirt_unisex"]
    # Track accounts already notified about hitting their warm-up cap in this
    # run, so we send at most one warmup_capped notification per account
    # (instead of one per skipped design × product_type combination).
    warmup_notified: set[int] = set()
    for platform_name in targets:
        accounts = _select_accounts(db, campaign, platform_name)
        if not accounts:
            logger.info("No active account for %s — skip", platform_name)
            continue
        for account in accounts:
            for design in designs:
                for ptype in product_types:
                    _publish_one(db, campaign, account, design, ptype, warmup_notified)
                    published_now = (
                        db.query(Product)
                        .filter_by(
                            design_id=design.id,
                            platform_account_id=account.id,
                            product_type=ptype,
                            status="published",
                        )
                        .first()
                    )
                    if published_now:
                        published += 1
    db.commit()
    return published


def _publish_one(
    db,
    campaign: Campaign,
    account,
    design: Design,
    product_id: str,
    warmup_notified: set[int] | None = None,
) -> None:
    # Defense-in-depth: even though _select_accounts pre-filters paused/banned
    # accounts, the account row could have been flipped to paused/banned mid-run
    # (e.g. by a webhook handler). Re-check health here and skip silently if so.
    now = datetime.now(UTC)
    if account.health_status in ("paused", "banned") or (
        account.paused_until is not None and account.paused_until > now
    ):
        logger.warning(
            "skipping publish for account %s — health=%s paused_until=%s",
            account.id,
            account.health_status,
            account.paused_until,
        )
        return
    # Reset stale counter from previous day before checking the warmup gate.
    today = now.date()
    if account.today_publish_date != today:
        account.today_publish_date = today
        account.today_publish_count = 0
    # Warm-up gate: respect daily cap + min spacing per account.
    decision = decide_publish(
        created_at=account.created_at,
        override_age_days=account.account_age_days_override,
        user_override_cap=account.daily_publish_cap_override,
        today_published=account.today_publish_count or 0,
        last_publish_at=account.last_publish_at,
    )
    if not decision.allowed:
        logger.info(
            "warmup gate blocked publish for account %s: %s", account.id, decision.reason
        )
        # Only notify the first time we hit the cap for this account in this run;
        # otherwise a campaign with N designs × M product types would generate
        # N*M nearly-identical notifications.
        already_notified = warmup_notified is not None and account.id in warmup_notified
        if not already_notified:
            try:
                notify(
                    db,
                    user_id=campaign.user_id,
                    kind="warmup_capped",
                    title=f"Warm-up: bỏ qua publish cho account {account.label or account.id}",
                    body=decision.reason,
                    severity="info",
                    payload={
                        "account_id": account.id,
                        "today": decision.today_published,
                        "cap": decision.cap,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("notify warmup failed: %s", exc)
            if warmup_notified is not None:
                warmup_notified.add(account.id)
        return

    blueprint = get_blueprint(product_id)
    price = (
        blueprint.suggested_retail_usd
        if blueprint and campaign.base_price_usd in (0, 19.99)
        else campaign.base_price_usd
    )
    seo = generate_seo(
        keyword=design.title,
        niche=campaign.niche or design.title,
        product_id=product_id,
        user_id=campaign.user_id,
        db=db,
    ) if campaign.seo_auto else None

    title = seo.title if seo else design.title
    description = (
        seo.description
        if seo
        else f"{design.title} — original design for {campaign.niche or 'enthusiasts'}."
    )
    tags = (
        seo.tags
        if seo
        else [t.strip() for t in (campaign.niche or "").split(",") if t.strip()]
    ) or [campaign.niche or "trendy"]

    # Publish always uses the highest-resolution variant available so the
    # uploaded image meets Printify's 300 DPI / 4500x5400 requirement.
    src_rel = design.upscaled_path or design.bg_removed_path or design.file_path
    design_abs = str(Path(settings.media_root) / src_rel)
    try:
        adapter = get_platform(account.platform, account)
        res = adapter.publish(
            design_path=design_abs,
            title=title,
            description=description,
            tags=tags,
            price_usd=price,
            product_type=product_id,
        )
        db.add(
            Product(
                design_id=design.id,
                platform_account_id=account.id,
                external_id=res.external_id,
                url=res.url,
                product_type=product_id,
                title=title,
                description=description,
                tags=tags,
                price_usd=price,
                status=res.status,
                error=res.error,
                published_at=datetime.now(UTC) if res.status == "published" else None,
            )
        )
        if res.status == "published":
            _bump_warmup_counter(account)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Publish failed: %s", exc)
        db.add(
            Product(
                design_id=design.id,
                platform_account_id=account.id,
                product_type=product_id,
                title=title,
                description=description,
                tags=tags,
                price_usd=price,
                status="failed",
                error=str(exc)[:500],
            )
        )
        db.commit()


def _bump_warmup_counter(account: PlatformAccount) -> None:
    today = datetime.now(UTC).date()
    if account.today_publish_date != today:
        account.today_publish_date = today
        account.today_publish_count = 0
    account.today_publish_count = (account.today_publish_count or 0) + 1
    account.last_publish_at = datetime.now(UTC)
