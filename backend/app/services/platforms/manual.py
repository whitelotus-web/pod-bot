"""Manual / semi-automated platform adapters.

Several platforms (RedBubble, Society6, Amazon Merch on Demand,
Spreadshirt) intentionally do **not** expose a public bulk-listing API.
For these we publish in two stages:

1. **Export bundle**: take the upscaled design + Etsy-style SEO bundle
   and zip them into a ready-to-upload package on disk.
2. **Telegram nudge**: notify the seller that an export is ready, with a
   link to the zip and a checklist of what to paste where.

This keeps the rest of the pipeline uniform — the seller still gets
all the AI / SEO / upscaler benefits, just with a 30-second manual
upload at the end. We surface this as the ``MANUAL_EXPORT`` status
on PublishResult so the dashboard can highlight it.
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
import zipfile
from pathlib import Path

from app.core.config import settings
from app.services.platforms.base import PODPlatform, PublishResult

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(settings.media_root) / "manual_exports"


class _ManualPlatform(PODPlatform):
    """Common implementation for export-only platforms."""

    LABEL = "manual"

    def __init__(self, account):
        self.account = account
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    def test_connection(self) -> bool:
        return True  # No remote API to test against.

    def _build_export(
        self,
        *,
        design_path: str,
        title: str,
        description: str,
        tags: list[str],
        price_usd: float,
        product_type: str,
    ) -> Path:
        slug = "".join(c if c.isalnum() else "-" for c in title.lower())[:40] or "design"
        # uuid4 keeps concurrent calls in the same process from colliding on
        # the same temp directory (PID alone is not unique under threading).
        bundle_dir = EXPORT_DIR / f"{self.name}-{slug}-{uuid.uuid4().hex[:8]}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        try:
            # 1. Copy the design alongside the metadata.
            target = bundle_dir / Path(design_path).name
            shutil.copyfile(design_path, target)

            # 2. Write the SEO + listing payload as JSON for the seller to
            # paste into RedBubble / Society6 fields.
            (bundle_dir / "listing.json").write_text(
                json.dumps(
                    {
                        "platform": self.name,
                        "title": title,
                        "description": description,
                        "tags": tags,
                        "price_usd": price_usd,
                        "product_type": product_type,
                        "instructions_url": self._instructions_url(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            # 3. Zip the bundle so it's a single artefact to share.
            zip_path = bundle_dir.with_suffix(".zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in bundle_dir.iterdir():
                    zf.write(p, arcname=p.name)
            shutil.rmtree(bundle_dir)
            return zip_path
        except Exception:
            shutil.rmtree(bundle_dir, ignore_errors=True)
            raise

    def _instructions_url(self) -> str:
        return ""

    def publish(
        self,
        *,
        design_path: str,
        title: str,
        description: str,
        tags: list[str],
        price_usd: float,
        product_type: str = "tshirt",
    ) -> PublishResult:
        try:
            zip_path = self._build_export(
                design_path=design_path,
                title=title,
                description=description,
                tags=tags,
                price_usd=price_usd,
                product_type=product_type,
            )
            return PublishResult(
                external_id=zip_path.name,
                url=f"/media/manual_exports/{zip_path.name}",
                # We use a pseudo-status so the dashboard can route the
                # listing into the "Pending manual upload" tray. Pipelines
                # treat anything other than "published" as not-yet-shipped.
                status="manual_export",
                raw={"export_path": str(zip_path)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Manual export failed for %s", self.name)
            return PublishResult(status="failed", error=str(exc))


class RedBubblePlatform(_ManualPlatform):
    name = "redbubble"
    LABEL = "RedBubble"

    def _instructions_url(self) -> str:
        return "https://www.redbubble.com/upload"


class Society6Platform(_ManualPlatform):
    name = "society6"
    LABEL = "Society6"

    def _instructions_url(self) -> str:
        return "https://society6.com/studio/uploads"


class AmazonMerchPlatform(_ManualPlatform):
    name = "amazon_merch"
    LABEL = "Amazon Merch on Demand"

    def _instructions_url(self) -> str:
        return "https://merch.amazon.com/dashboard"


class SpreadshirtPlatform(_ManualPlatform):
    name = "spreadshirt"
    LABEL = "Spreadshirt"

    def _instructions_url(self) -> str:
        return "https://www.spreadshirt.com/create-your-own"
