"""Video generation orchestration handler."""

from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, cast

from PIL import Image

from api_types import GenerateVideoRequest, GenerateVideoResponse
from _routes._errors import HTTPError
from handlers.base import StateHandlerBase
from handlers.generation_handler import GenerationHandler
from handlers.pipelines_handler import PipelinesHandler
from handlers.text_handler import TextHandler
from services.interfaces import (
    FastNativeVideoPipeline,
    FastVideoPipeline,
    LTXAPIClient,
    ProNativeVideoPipeline,
    ProVideoPipeline,
    VideoPipelineModelType,
)
from state.app_state_types import AppState

if TYPE_CHECKING:
    from runtime_config.runtime_config import RuntimeConfig

logger = logging.getLogger(__name__)

FORCED_API_MODEL_MAP: dict[str, str] = {
    "fast": "ltx-2-fast",
    "pro": "ltx-2-pro",
}
FORCED_API_RESOLUTION_MAP: dict[str, str] = {
    "1080p": "1920x1080",
    "1440p": "2560x1440",
    "2160p": "3840x2160",
}
FORCED_API_ALLOWED_DURATIONS = {6, 8, 10}
FORCED_API_ALLOWED_FPS = {25, 50}


class VideoGenerationHandler(StateHandlerBase):
    def __init__(
        self,
        state: AppState,
        lock: RLock,
        generation_handler: GenerationHandler,
        pipelines_handler: PipelinesHandler,
        text_handler: TextHandler,
        ltx_api_client: LTXAPIClient,
        outputs_dir: Path,
        config: RuntimeConfig,
        camera_motion_prompts: dict[str, str],
        default_negative_prompt: str,
    ) -> None:
        super().__init__(state, lock)
        self._generation = generation_handler
        self._pipelines = pipelines_handler
        self._text = text_handler
        self._ltx_api_client = ltx_api_client
        self._outputs_dir = outputs_dir
        self._config = config
        self._camera_motion_prompts = camera_motion_prompts
        self._default_negative_prompt = default_negative_prompt

    def generate(self, req: GenerateVideoRequest) -> GenerateVideoResponse:
        if self._config.force_api_generations:
            return self._generate_forced_api(req)

        if self._generation.is_generation_running():
            raise HTTPError(409, "Generation already in progress")

        resolution = req.resolution
        model_type = req.model

        duration = int(float(req.duration))
        fps = int(float(req.fps))

        use_upsampler = resolution == "1080p"
        if not use_upsampler:
            if model_type == "fast":
                model_type = "fast-native"
                logger.info("Resolution %s - using fast-native pipeline (no upsampler)", resolution)
            elif model_type == "pro":
                model_type = "pro-native"
                logger.info("Resolution %s - using pro-native pipeline (no upsampler)", resolution)
        else:
            logger.info("Resolution %s - using 2-stage pipeline with upsampler", resolution)

        resolution_map = {
            "540p": (960, 544),
            "720p": (1280, 704),
            "1080p": (960, 544),
        }
        width, height = resolution_map.get(resolution, (960, 544))

        num_frames = ((duration * fps) // 8) * 8 + 1
        if num_frames < 9:
            num_frames = 9

        image = None
        if req.imagePath:
            if not os.path.isfile(req.imagePath):
                raise HTTPError(400, f"Image file not found: {req.imagePath}")

            img = Image.open(req.imagePath).convert("RGB")
            img_w, img_h = img.size
            target_ratio = width / height
            img_ratio = img_w / img_h

            if img_ratio > target_ratio:
                new_h = height
                new_w = int(img_w * (height / img_h))
            else:
                new_w = width
                new_h = int(img_h * (width / img_w))

            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - width) // 2
            top = (new_h - height) // 2
            image = resized.crop((left, top, left + width, top + height))
            logger.info("Image: %s %sx%s -> %sx%s", req.imagePath, img_w, img_h, width, height)

        generation_id = uuid.uuid4().hex[:8]

        settings = self.state.app_settings.model_copy(deep=True)
        if settings.seed_locked:
            seed = settings.locked_seed
            logger.info("Using locked seed: %s", seed)
        else:
            seed = int(time.time()) % 2147483647

        try:
            self._pipelines.load_gpu_pipeline(cast(VideoPipelineModelType, model_type), should_warm=False)
            self._generation.start_generation(generation_id)

            output_path = self.generate_video(
                prompt=req.prompt,
                image=image,
                height=height,
                width=width,
                num_frames=num_frames,
                fps=fps,
                seed=seed,
                model_type=cast(VideoPipelineModelType, model_type),
                camera_motion=req.cameraMotion,
                negative_prompt=req.negativePrompt,
            )

            self._generation.complete_generation(output_path)
            return GenerateVideoResponse(status="complete", video_path=output_path)

        except Exception as e:
            self._generation.fail_generation(str(e))
            if "cancelled" in str(e).lower():
                logger.info("Generation cancelled by user")
                return GenerateVideoResponse(status="cancelled")

            raise HTTPError(500, str(e)) from e

    def generate_video(
        self,
        prompt: str,
        image: Image.Image | None,
        height: int,
        width: int,
        num_frames: int,
        fps: float,
        seed: int,
        model_type: VideoPipelineModelType,
        camera_motion: str,
        negative_prompt: str,
    ) -> str:
        if self._generation.is_generation_cancelled():
            raise RuntimeError("Generation was cancelled")

        if not self._config.model_path("checkpoint").exists():
            raise RuntimeError("Models not downloaded. Please download the AI models first using the Model Status menu.")

        total_steps = 8 if model_type in ("fast", "fast-native") else self.state.app_settings.pro_model.steps

        self._generation.update_progress("loading_model", 5, 0, total_steps)
        pipeline_state = self._pipelines.load_gpu_pipeline(model_type, should_warm=False)
        self._generation.update_progress("encoding_text", 10, 0, total_steps)

        enhanced_prompt = prompt + self._camera_motion_prompts.get(camera_motion, "")

        images: list[tuple[str, int, float]] = []
        temp_image_path: str | None = None
        if image is not None:
            temp_image_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            image.save(temp_image_path)
            images = [(temp_image_path, 0, 1.0)]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self._outputs_dir / f"ltx2_video_{timestamp}_{uuid.uuid4().hex[:8]}.mp4"

        try:
            self._text.prepare_text_encoding(enhanced_prompt)

            self._generation.update_progress("inference", 15, 0, total_steps)

            divisor = 32 if model_type == "pro-native" else 64
            height = round(height / divisor) * divisor
            width = round(width / divisor) * divisor

            pro_steps = self.state.app_settings.pro_model.steps
            neg = negative_prompt if negative_prompt else self._default_negative_prompt

            if model_type in {"fast", "fast-native"}:
                fast_pipeline = cast(FastVideoPipeline | FastNativeVideoPipeline, pipeline_state.pipeline)
                fast_pipeline.generate(
                    prompt=enhanced_prompt,
                    seed=seed,
                    height=height,
                    width=width,
                    num_frames=num_frames,
                    frame_rate=fps,
                    images=images,
                    output_path=str(output_path),
                )
            else:
                pro_pipeline = cast(ProVideoPipeline | ProNativeVideoPipeline, pipeline_state.pipeline)
                pro_pipeline.generate(
                    prompt=enhanced_prompt,
                    negative_prompt=neg,
                    seed=seed,
                    height=height,
                    width=width,
                    num_frames=num_frames,
                    frame_rate=fps,
                    num_inference_steps=pro_steps,
                    images=images,
                    output_path=str(output_path),
                )

            if self._generation.is_generation_cancelled():
                if output_path.exists():
                    output_path.unlink()
                raise RuntimeError("Generation was cancelled")

            self._generation.update_progress("complete", 100, total_steps, total_steps)
            return str(output_path)
        finally:
            self._text.clear_api_embeddings()
            if temp_image_path and os.path.exists(temp_image_path):
                os.unlink(temp_image_path)

    def _generate_forced_api(self, req: GenerateVideoRequest) -> GenerateVideoResponse:
        if self._generation.is_generation_running():
            raise HTTPError(409, "Generation already in progress")

        generation_id = uuid.uuid4().hex[:8]
        self._generation.start_api_generation(generation_id)

        has_input_image = bool(req.imagePath)

        try:
            self._generation.update_progress("validating_request", 5, None, None)

            api_key = self.state.app_settings.ltx_api_key.strip()
            logger.info("Forced API generation route selected (key_present=%s)", bool(api_key))
            if not api_key:
                raise HTTPError(400, "PRO_API_KEY_REQUIRED")

            requested_model = req.model.strip().lower()
            api_model_id = FORCED_API_MODEL_MAP.get(requested_model)
            if api_model_id is None:
                raise HTTPError(400, "INVALID_FORCED_API_MODEL")

            resolution_label = req.resolution
            api_resolution = FORCED_API_RESOLUTION_MAP.get(resolution_label)
            if api_resolution is None:
                raise HTTPError(400, "INVALID_FORCED_API_RESOLUTION")

            duration = self._parse_forced_numeric_field(req.duration, "INVALID_FORCED_API_DURATION")
            if duration not in FORCED_API_ALLOWED_DURATIONS:
                raise HTTPError(400, "INVALID_FORCED_API_DURATION")

            fps = self._parse_forced_numeric_field(req.fps, "INVALID_FORCED_API_FPS")
            if fps not in FORCED_API_ALLOWED_FPS:
                raise HTTPError(400, "INVALID_FORCED_API_FPS")

            generate_audio = self._parse_audio_flag(req.audio)
            prompt = req.prompt

            if self._generation.is_generation_cancelled():
                raise RuntimeError("Generation was cancelled")

            if has_input_image:
                image_path = req.imagePath
                if image_path is None:
                    raise HTTPError(400, "Image path is required for image-to-video")
                if not os.path.isfile(image_path):
                    raise HTTPError(400, f"Image file not found: {image_path}")

                self._generation.update_progress("uploading_image", 20, None, None)
                self._generation.update_progress("inference", 55, None, None)
                video_bytes = self._ltx_api_client.generate_image_to_video(
                    api_key=api_key,
                    prompt=prompt,
                    image_path=image_path,
                    model=api_model_id,
                    resolution=api_resolution,
                    duration=float(duration),
                    fps=float(fps),
                    generate_audio=generate_audio,
                )
                self._generation.update_progress("downloading_output", 85, None, None)
            else:
                self._generation.update_progress("inference", 55, None, None)
                video_bytes = self._ltx_api_client.generate_text_to_video(
                    api_key=api_key,
                    prompt=prompt,
                    model=api_model_id,
                    resolution=api_resolution,
                    duration=float(duration),
                    fps=float(fps),
                    generate_audio=generate_audio,
                )
                self._generation.update_progress("downloading_output", 85, None, None)

            if self._generation.is_generation_cancelled():
                raise RuntimeError("Generation was cancelled")

            output_path = self._write_forced_api_video(video_bytes)
            if self._generation.is_generation_cancelled():
                output_path.unlink(missing_ok=True)
                raise RuntimeError("Generation was cancelled")

            self._generation.update_progress("complete", 100, None, None)
            self._generation.complete_generation(str(output_path))
            return GenerateVideoResponse(status="complete", video_path=str(output_path))
        except HTTPError as e:
            self._generation.fail_generation(e.detail)
            raise
        except Exception as e:
            self._generation.fail_generation(str(e))
            if "cancelled" in str(e).lower():
                logger.info("Generation cancelled by user")
                return GenerateVideoResponse(status="cancelled")
            raise HTTPError(500, str(e)) from e

    def _write_forced_api_video(self, video_bytes: bytes) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self._outputs_dir / f"ltx2_video_{timestamp}_{uuid.uuid4().hex[:8]}.mp4"
        output_path.write_bytes(video_bytes)
        return output_path

    @staticmethod
    def _parse_forced_numeric_field(raw_value: str, error_detail: str) -> int:
        try:
            return int(float(raw_value))
        except (TypeError, ValueError):
            raise HTTPError(400, error_detail) from None

    @staticmethod
    def _parse_audio_flag(audio_value: str | bool) -> bool:
        if isinstance(audio_value, bool):
            return audio_value
        normalized = audio_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}
