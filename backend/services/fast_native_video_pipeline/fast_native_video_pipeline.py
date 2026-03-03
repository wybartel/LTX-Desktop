"""Fast native video pipeline protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

from api_types import ImageConditioningInput

if TYPE_CHECKING:
    import torch


class FastNativeVideoPipeline(Protocol):
    pipeline_kind: ClassVar[Literal["fast-native"]]

    @staticmethod
    def create(
        checkpoint_path: str,
        gemma_root: str | None,
        device: torch.device,
    ) -> "FastNativeVideoPipeline":
        ...

    def generate(
        self,
        prompt: str,
        seed: int,
        height: int,
        width: int,
        num_frames: int,
        frame_rate: float,
        images: list[ImageConditioningInput],
        output_path: str,
    ) -> None:
        ...

    def warmup(self, output_path: str) -> None:
        ...

    def compile_transformer(self) -> None:
        ...
