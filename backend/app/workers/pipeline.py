"""The main pipeline: keyword → design → mockup → publish."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from slugify import slugify

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Campaign, Design, Keyword, Mockup, PlatformAccount, Product, RunLog
from app.services.ai import get_engine
from app.services.keywords import KeywordAggregator
from app.services.mockup import PillowMockup
from app.services.platforms import get_platform
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.pipeline.run_campaign")
def run_campaign(self, campaign_id: int, force_auto: bool | None = None) -> dict:
    """End-to-end run for a single campaign.

    force_auto=True  → đăng luôn (full auto)
    force_auto=False → chỉ tạo design & mockup (semi)
    force_auto=None  → dùng Campaign.auto_mode
    """
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
            auto_mode = "full" if force_auto else ("semi" if force_auto is False else campaign.auto_mode)

            # 1) Keywords
            kw_log = _log(db, campaign_id, "keywords", "running")
            terms = _fetch_keywords(db, campaign)
            kw_log.status = "success"
            kw_log.finished_at = datetime.now(UTC)
            kw_log.data = {"count": len(terms)}
            db.commit()

            # 2) Designs + mockups for top-N keywords
            design_log = _log(db, campaign_id, "design", "running")
            created_designs: list[Design] = []
            top_terms = terms[: max(1, campaign.designs_per_keyword)]
            # Reuse a Printify account (if any) for mockup generation — its
            # mockups are far more polished than the local Pillow fallback.
            printify_account = (
                db.query(PlatformAccount)
                .filter_by(user_id=campaign.user_id, platform="printify", is_active=True)
                .first()
            )
            for kw in top_terms:
                try:
                    designs = _generate_designs(db, campaign, kw)
                    for d in designs:
                        _render_mockups(
                            db,
                            d,
                            campaign.product_types or ["tshirt"],
                            printify_account=printify_account,
                        )
                        created_designs.append(d)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("design generation failed for %s: %s", kw.term, exc)
            design_log.status = "success"
            design_log.finished_at = datetime.now(UTC)
            design_log.data = {"count": len(created_designs)}
            db.commit()

            # 3) Publish (only if auto_mode=="full")
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
    engine = get_engine(campaign.ai_engine)
    base_prompt = engine.design_prompt(
        keyword.term, niche=campaign.niche, style=campaign.style_prompt
    )
    out: list[Design] = []
    Path(settings.media_root, "designs").mkdir(parents=True, exist_ok=True)
    for i in range(max(1, campaign.designs_per_keyword)):
        prompt = base_prompt + f" Variation {i + 1}."
        try:
            img = engine.generate(prompt, model=campaign.ai_model)
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI generate failed: %s", exc)
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


def _render_mockups(
    db,
    design: Design,
    product_types: list[str],
    printify_account: PlatformAccount | None = None,
) -> None:
    """Render mockups for a design.

    Strategy:
      1. If a Printify account is connected, the publish stage will already
         produce photorealistic mockups — we still keep a local Pillow render
         as a quick preview for the dashboard (no extra API quota).
      2. Otherwise, Pillow renders are the only preview available.
    """
    mocker = PillowMockup()
    design_abs = Path(settings.media_root) / design.file_path
    for ptype in product_types:
        template = {
            "tshirt": "tshirt_white",
            "tshirt_black": "tshirt_black",
            "hoodie": "hoodie_gray",
        }.get(ptype, "tshirt_white")
        try:
            out_path = mocker.render(str(design_abs), template=template)
            rel = Path(out_path).relative_to(settings.media_root)
            m = Mockup(
                design_id=design.id,
                product_type=ptype,
                template=template,
                file_path=str(rel),
                source="printify" if printify_account else "pillow",
            )
            db.add(m)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mockup render failed: %s", exc)
    db.commit()


def _publish_all(db, campaign: Campaign, designs: list[Design]) -> int:
    published = 0
    targets = campaign.target_platforms or []
    for platform_name in targets:
        accounts = (
            db.query(PlatformAccount)
            .filter_by(
                user_id=campaign.user_id,
                platform=platform_name,
                is_active=True,
            )
            .all()
        )
        if not accounts:
            logger.info("No active account for %s — skip", platform_name)
            continue
        account = accounts[0]
        for design in designs:
            try:
                adapter = get_platform(platform_name, account)
                design_abs = str(Path(settings.media_root) / design.file_path)
                tags = [t.strip() for t in (campaign.niche or "").split(",") if t.strip()]
                res = adapter.publish(
                    design_path=design_abs,
                    title=design.title,
                    description=(
                        f"{design.title} — một thiết kế độc đáo cho {campaign.niche or 'người sành điệu'}. "
                        "Chất liệu cotton cao cấp, in theo yêu cầu."
                    ),
                    tags=tags or [campaign.niche or "trendy"],
                    price_usd=campaign.base_price_usd,
                )
                product = Product(
                    design_id=design.id,
                    platform_account_id=account.id,
                    external_id=res.external_id,
                    url=res.url,
                    title=design.title,
                    description="",
                    tags=tags,
                    price_usd=campaign.base_price_usd,
                    status=res.status,
                    error=res.error,
                    published_at=datetime.now(UTC) if res.status == "published" else None,
                )
                db.add(product)
                if res.status == "published":
                    published += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("Publish failed on %s: %s", platform_name, exc)
    db.commit()
    return published
