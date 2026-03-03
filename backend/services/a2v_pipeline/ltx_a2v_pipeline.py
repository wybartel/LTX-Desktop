"""LTX A2V (Audio-to-Video) pipeline wrapper."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import torch

from api_types import ImageConditioningInput
from services.ltx_pipeline_common import default_guiders, default_tiling_config, encode_video_output, video_chunks_number
from services.services_utils import AudioOrNone, TilingConfigType, device_supports_fp8


class LTXa2vPipeline:
    @staticmethod
    def create(
        checkpoint_path: str,
        gemma_root: str | None,
        upsampler_path: str,
        distilled_lora_path: str,
        device: torch.device,
    ) -> "LTXa2vPipeline":
        return LTXa2vPipeline(
            checkpoint_path=checkpoint_path,
            gemma_root=gemma_root,
            upsampler_path=upsampler_path,
            distilled_lora_path=distilled_lora_path,
            device=device,
        )

    def __init__(
        self,
        checkpoint_path: str,
        gemma_root: str | None,
        upsampler_path: str,
        distilled_lora_path: str,
        device: torch.device,
    ) -> None:
        from ltx_core.loader.primitives import LoraPathStrengthAndSDOps
        from ltx_core.loader.sd_ops import LTXV_LORA_COMFY_RENAMING_MAP
        from ltx_core.quantization import QuantizationPolicy
        from ltx_pipelines.a2vid_two_stage import A2VidPipelineTwoStage

        self.pipeline = A2VidPipelineTwoStage(
            checkpoint_path=checkpoint_path,
            gemma_root=cast(str, gemma_root),
            spatial_upsampler_path=upsampler_path,
            distilled_lora=[
                LoraPathStrengthAndSDOps(distilled_lora_path, 1.0, LTXV_LORA_COMFY_RENAMING_MAP),
            ],
            loras=[],
            device=cast(str, device),
            quantization=QuantizationPolicy.fp8_cast() if device_supports_fp8(device) else None,
        )

    def _run_inference(
        self,
        prompt: str,
        negative_prompt: str,
        seed: int,
        height: int,
        width: int,
        num_frames: int,
        frame_rate: float,
        num_inference_steps: int,
        images: list[ImageConditioningInput],
        audio_path: str,
        audio_start_time: float,
        audio_max_duration: float | None,
        tiling_config: TilingConfigType,
    ) -> tuple[torch.Tensor | Iterator[torch.Tensor], AudioOrNone]:
        video_guider_params = default_guiders()[0]
        return self.pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            height=height,
            width=width,
            num_frames=num_frames,
            frame_rate=frame_rate,
            num_inference_steps=num_inference_steps,
            video_guider_params=video_guider_params,
            images=[(img.path, img.frame_idx, img.strength) for img in images],
            audio_path=audio_path,
            audio_start_time=audio_start_time,
            audio_max_duration=audio_max_duration,
            tiling_config=tiling_config,
        )

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        seed: int,
        height: int,
        width: int,
        num_frames: int,
        frame_rate: float,
        num_inference_steps: int,
        images: list[ImageConditioningInput],
        audio_path: str,
        audio_start_time: float,
        audio_max_duration: float | None,
        output_path: str,
    ) -> None:
        tiling_config = default_tiling_config()
        video, audio = self._run_inference(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            height=height,
            width=width,
            num_frames=num_frames,
            frame_rate=frame_rate,
            num_inference_steps=num_inference_steps,
            images=images,
            audio_path=audio_path,
            audio_start_time=audio_start_time,
            audio_max_duration=audio_max_duration,
            tiling_config=tiling_config,
        )
        chunks = video_chunks_number(num_frames, tiling_config)
        encode_video_output(video=video, audio=audio, fps=int(frame_rate), output_path=output_path, video_chunks_number_value=chunks)
