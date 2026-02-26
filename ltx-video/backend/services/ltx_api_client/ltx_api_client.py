"""LTX API client service protocol."""

from __future__ import annotations

from typing import Protocol

from api_types import VideoCameraMotion


class LTXAPIClient(Protocol):
    def generate_text_to_video(
        self,
        *,
        api_key: str,
        prompt: str,
        model: str,
        resolution: str,
        duration: float,
        fps: float,
        generate_audio: bool,
        camera_motion: VideoCameraMotion = "none",
    ) -> bytes:
        ...

    def generate_image_to_video(
        self,
        *,
        api_key: str,
        prompt: str,
        image_path: str,
        model: str,
        resolution: str,
        duration: float,
        fps: float,
        generate_audio: bool,
        camera_motion: VideoCameraMotion = "none",
    ) -> bytes:
        ...
