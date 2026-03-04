"""LTX retake pipeline wrapper."""

from __future__ import annotations

import importlib
from typing import cast

from ltx_core.components.guiders import MultiModalGuiderParams
from ltx_core.loader import LoraPathStrengthAndSDOps
from ltx_core.model.video_vae import TilingConfig, get_video_chunks_number
from ltx_core.quantization import QuantizationPolicy
from ltx_core.types import Audio
from ltx_pipelines.utils.media_io import encode_video, get_videostream_metadata
import torch

from services.retake_pipeline.retake_pipeline import RetakePipeline


class LTXRetakePipeline:
    @staticmethod
    def create(
        checkpoint_path: str,
        gemma_root: str | None,
        device: torch.device,
        *,
        loras: list[LoraPathStrengthAndSDOps] | None = None,
        quantization: QuantizationPolicy | None = None,
    ) -> RetakePipeline:
        return LTXRetakePipeline(
            checkpoint_path=checkpoint_path,
            gemma_root=gemma_root,
            device=device,
            loras=loras or [],
            quantization=quantization,
        )

    def __init__(
        self,
        checkpoint_path: str,
        gemma_root: str | None,
        device: torch.device,
        *,
        loras: list[LoraPathStrengthAndSDOps],
        quantization: QuantizationPolicy | None,
    ) -> None:
        try:
            module = importlib.import_module("ltx_pipelines.retake")
        except Exception:  # pragma: no cover - fallback for alternate module name
            module = importlib.import_module("ltx_pipelines.retake_pipeline")

        pipeline_class = getattr(module, "RetakePipeline")
        # RetakePipeline accepts gemma_root even if it's None; the text encoder
        # patching will supply API embeddings when available.
        self._pipeline = pipeline_class(
            checkpoint_path=checkpoint_path,
            gemma_root=gemma_root,
            loras=loras,
            device=device,
            quantization=quantization,
        )

    def generate(
        self,
        *,
        video_path: str,
        prompt: str,
        start_time: float,
        end_time: float,
        seed: int,
        output_path: str,
        negative_prompt: str = "",
        num_inference_steps: int = 40,
        video_guider_params: MultiModalGuiderParams | None = None,
        audio_guider_params: MultiModalGuiderParams | None = None,
        regenerate_video: bool = True,
        regenerate_audio: bool = True,
        enhance_prompt: bool = False,
        distilled: bool = True,
    ) -> None:
        fps, num_frames, _, _ = get_videostream_metadata(video_path)
        video_iter, audio = self._pipeline(
            video_path=video_path,
            prompt=prompt,
            start_time=start_time,
            end_time=end_time,
            seed=seed,
            negative_prompt=negative_prompt,
            num_inference_steps=num_inference_steps,
            video_guider_params=video_guider_params,
            audio_guider_params=audio_guider_params,
            regenerate_video=regenerate_video,
            regenerate_audio=regenerate_audio,
            enhance_prompt=enhance_prompt,
            distilled=distilled,
        )
        audio_out = cast(Audio | None, audio)
        tiling_config = TilingConfig.default()
        video_chunks = get_video_chunks_number(num_frames, tiling_config)
        encode_video(
            video=video_iter,
            fps=int(fps),
            audio=audio_out,
            output_path=output_path,
            video_chunks_number=video_chunks,
        )
