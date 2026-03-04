"""Retake API orchestration handler."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from threading import RLock

from api_types import RetakeRequest, RetakeResponse
from _routes._errors import HTTPError
from handlers.base import StateHandlerBase
from services.ltx_api_client.ltx_api_client import LTXAPIClientError
from services.interfaces import LTXAPIClient
from state.app_state_types import AppState

class RetakeHandler(StateHandlerBase):
    def __init__(self, state: AppState, lock: RLock, ltx_api_client: LTXAPIClient, outputs_dir: Path) -> None:
        super().__init__(state, lock)
        self._ltx_api_client = ltx_api_client
        self._outputs_dir = outputs_dir

    def run(self, req: RetakeRequest) -> RetakeResponse:
        video_path = req.video_path
        start_time = req.start_time
        duration = req.duration
        prompt = req.prompt
        mode = req.mode

        if not video_path:
            raise HTTPError(400, "Missing video_path parameter")
        if duration < 2:
            raise HTTPError(400, "duration must be at least 2 seconds")

        video_file = Path(video_path)
        if not video_file.exists():
            raise HTTPError(400, f"Video file not found: {video_path}")

        api_key = self.state.app_settings.ltx_api_key
        if not api_key:
            raise HTTPError(400, "LTX API key not configured. Set it in Settings.")

        try:
            result = self._ltx_api_client.retake(
                api_key=api_key,
                video_path=str(video_file),
                start_time=start_time,
                duration=duration,
                prompt=prompt,
                mode=mode,
            )
        except LTXAPIClientError as exc:
            raise HTTPError(exc.status_code, exc.detail) from exc

        if result.video_bytes is not None:
            output = self._outputs_dir / f"retake_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp4"
            with open(output, "wb") as out:
                out.write(result.video_bytes)
            return RetakeResponse(status="complete", video_path=str(output))

        if result.result_payload is not None:
            return RetakeResponse(status="complete", result=result.result_payload)

        raise HTTPError(500, "Retake API returned no result")
