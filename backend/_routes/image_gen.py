"""Route handlers for /api/generate-image, /api/edit-image."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_types import EditImageRequest, GenerateImageRequest, GenerateImageResponse
from state import get_state_service
from app_handler import AppHandler

router = APIRouter(prefix="/api", tags=["image"])


@router.post("/generate-image", response_model=GenerateImageResponse)
def route_generate_image(
    req: GenerateImageRequest,
    handler: AppHandler = Depends(get_state_service),
) -> GenerateImageResponse:
    """POST /api/generate-image."""
    return handler.image_generation.generate(req)


@router.post("/edit-image", response_model=GenerateImageResponse)
def route_edit_image(
    req: EditImageRequest,
    handler: AppHandler = Depends(get_state_service),
) -> GenerateImageResponse:
    """POST /api/edit-image — accepts JSON with filesystem paths."""
    return handler.image_generation.edit(req)
