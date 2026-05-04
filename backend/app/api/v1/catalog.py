"""Catalog of POD product blueprints + presets for the campaign form."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.services.catalog import list_catalog, list_presets

router = APIRouter()


@router.get("/products")
def get_catalog(_: User = Depends(get_current_user)) -> dict:
    return {
        "products": list_catalog(),
        "presets": list_presets(),
    }
