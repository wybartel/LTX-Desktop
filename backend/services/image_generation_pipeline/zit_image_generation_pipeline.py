"""Z-Image-Turbo image generation pipeline wrapper."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch
from diffusers import ZImageImg2ImgPipeline, ZImagePipeline
from PIL.Image import Image as PILImage

from services.services_utils import ImagePipelineOutputLike, PILImageType, get_device_type


@dataclass(slots=True)
class _ZImageOutput:
    images: Sequence[PILImageType]


class ZitImageGenerationPipeline:
    @staticmethod
    def create(
        model_path: str,
        device: str | None = None,
    ) -> "ZitImageGenerationPipeline":
        return ZitImageGenerationPipeline(model_path=model_path, device=device)

    def __init__(self, model_path: str, device: str | None = None) -> None:
        self._device: str | None = None
        self._cpu_offload_active = False
        self.pipeline = ZImagePipeline.from_pretrained(  # type: ignore[reportUnknownMemberType]
            model_path,
            torch_dtype=torch.bfloat16,
        )
        self._edit_pipeline: ZImageImg2ImgPipeline | None = None
        if device is not None:
            self.to(device)

    def _ensure_edit_pipeline(self) -> ZImageImg2ImgPipeline:
        if self._edit_pipeline is not None:
            return self._edit_pipeline
        self._edit_pipeline = ZImageImg2ImgPipeline.from_pipe(self.pipeline)  # type: ignore[reportUnknownMemberType]
        if self._cpu_offload_active:
            self._edit_pipeline.enable_model_cpu_offload()  # type: ignore[reportUnknownMemberType]
        return self._edit_pipeline

    def _resolve_generator_device(self) -> str:
        if self._cpu_offload_active:
            return "cuda"
        if self._device is not None:
            return self._device

        execution_device = getattr(self.pipeline, "_execution_device", None)
        return get_device_type(execution_device)

    @staticmethod
    def _normalize_output(output: object) -> ImagePipelineOutputLike:
        images = getattr(output, "images", None)
        if not isinstance(images, Sequence):
            raise RuntimeError("Unexpected ZIT pipeline output format: missing images sequence")

        validated_images: list[PILImageType] = []
        for image in images:
            if not isinstance(image, PILImage):
                raise RuntimeError("Unexpected ZIT pipeline output format: images must be PIL.Image instances")
            validated_images.append(image)

        return _ZImageOutput(images=validated_images)

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        height: int,
        width: int,
        guidance_scale: float,
        num_inference_steps: int,
        seed: int,
    ) -> ImagePipelineOutputLike:
        del guidance_scale
        generator = torch.Generator(device=self._resolve_generator_device()).manual_seed(seed)
        output = self.pipeline(  # type: ignore[reportUnknownMemberType]
            prompt=prompt,
            height=height,
            width=width,
            guidance_scale=0.0,
            num_inference_steps=num_inference_steps,
            generator=generator,
            output_type="pil",
            return_dict=True,
        )
        return self._normalize_output(output)

    @torch.inference_mode()
    def generate_edit(
        self,
        prompt: str,
        image: PILImageType | list[PILImageType],
        height: int,
        width: int,
        guidance_scale: float,
        num_inference_steps: int,
        seed: int,
    ) -> ImagePipelineOutputLike:
        del guidance_scale
        edit_pipe = self._ensure_edit_pipeline()
        generator = torch.Generator(device=self._resolve_generator_device()).manual_seed(seed)
        output = edit_pipe(  # type: ignore[reportUnknownMemberType]
            prompt=prompt,
            image=image,
            height=height,
            width=width,
            guidance_scale=0.0,
            num_inference_steps=num_inference_steps,
            generator=generator,
            output_type="pil",
            return_dict=True,
        )
        return self._normalize_output(output)

    def to(self, device: str) -> None:
        runtime_device = get_device_type(device)
        if runtime_device in ("cuda", "mps"):
            self.pipeline.enable_model_cpu_offload()  # type: ignore[reportUnknownMemberType]
            self._cpu_offload_active = True
            if self._edit_pipeline is not None:
                self._edit_pipeline.enable_model_cpu_offload()  # type: ignore[reportUnknownMemberType]
        else:
            self._cpu_offload_active = False
            self.pipeline.to(runtime_device)  # type: ignore[reportUnknownMemberType]
            if self._edit_pipeline is not None:
                self._edit_pipeline.to(runtime_device)  # type: ignore[reportUnknownMemberType]
        self._device = runtime_device
