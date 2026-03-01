"""Flux API client protocol for BFL image generation."""

from __future__ import annotations

from typing import Protocol


class FluxAPIClient(Protocol):
    def is_configured(self) -> bool:
        ...

    def generate_text_to_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int,
        num_inference_steps: int,
    ) -> bytes:
        ...

    def generate_image_edit(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int,
        num_inference_steps: int,
        input_images: list[bytes],
    ) -> bytes:
        ...
