"""Flux API client implementation for BFL endpoints."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, cast

from services.http_client.http_client import HTTPClient
from services.services_utils import JSONValue

logger = logging.getLogger(__name__)

BFL_API_BASE_URL = "https://api.bfl.ai"
BFL_MODEL_ENDPOINT = "/v1/flux-2-klein-4b"
BFL_RESULT_ENDPOINT = "/v1/get_result"

# TODO(press-release): replace temporary hardcoded key and remove this constant.
BFL_API_KEY = "bfl_JlyfiMNWBCElr9HViyWTND3gHywZKrXv"
_BFL_KEY_PLACEHOLDER_VALUES = {"", "REPLACE_WITH_BFL_API_KEY"}

_POLL_INTERVAL_SECONDS = 1.0
_POLL_TIMEOUT_SECONDS = 300.0


class FluxAPIClientImpl:
    def __init__(
        self,
        http: HTTPClient,
        *,
        bfl_api_base_url: str = BFL_API_BASE_URL,
        bfl_api_key: str = BFL_API_KEY,
    ) -> None:
        self._http = http
        self._base_url = bfl_api_base_url.rstrip("/")
        self._api_key = bfl_api_key.strip()

    def is_configured(self) -> bool:
        return self._api_key not in _BFL_KEY_PLACEHOLDER_VALUES

    def generate_text_to_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        seed: int,
        num_inference_steps: int,
    ) -> bytes:
        payload: dict[str, JSONValue] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "output_format": "png",
            "safety_tolerance": 2,
        }
        return self._submit_and_wait(payload=payload)

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
        payload: dict[str, JSONValue] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "output_format": "png",
            "safety_tolerance": 2,
        }

        for idx, image_bytes in enumerate(input_images, start=1):
            key = "input_image" if idx == 1 else f"input_image_{idx}"
            payload[key] = self._to_data_uri(image_bytes)

        return self._submit_and_wait(payload=payload)

    def _submit_and_wait(self, *, payload: dict[str, JSONValue]) -> bytes:
        if not self.is_configured():
            raise RuntimeError("BFL_API_KEY_NOT_CONFIGURED")

        submit_response = self._http.post(
            f"{self._base_url}{BFL_MODEL_ENDPOINT}",
            headers={"x-key": self._api_key, "Content-Type": "application/json"},
            json_payload=payload,
            timeout=120,
        )
        if submit_response.status_code != 200:
            detail = submit_response.text[:500] if submit_response.text else "Unknown error"
            raise RuntimeError(f"BFL submit failed ({submit_response.status_code}): {detail}")

        submit_payload = self._json_object(submit_response.json(), context="submit")
        polling_url = self._extract_polling_url(submit_payload)
        result_payload = self._poll_until_ready(polling_url)

        sample_url = self._extract_sample_url(result_payload)
        download = self._http.get(sample_url, timeout=120)
        if download.status_code != 200:
            detail = download.text[:500] if download.text else "Unknown error"
            raise RuntimeError(f"BFL image download failed ({download.status_code}): {detail}")
        if not download.content:
            raise RuntimeError("BFL image download returned empty body")
        return download.content

    def _poll_until_ready(self, polling_url: str) -> dict[str, Any]:
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        last_status = "pending"

        while time.monotonic() < deadline:
            response = self._http.get(polling_url, headers={"x-key": self._api_key}, timeout=60)
            if response.status_code != 200:
                detail = response.text[:500] if response.text else "Unknown error"
                raise RuntimeError(f"BFL result polling failed ({response.status_code}): {detail}")

            payload = self._json_object(response.json(), context="poll")
            status = str(payload.get("status", "")).strip()
            normalized_status = status.lower()
            if normalized_status in {"ready", "completed", "complete"}:
                return payload
            if (
                normalized_status in {"error", "failed", "task_not_found", "task not found"}
                or "moderat" in normalized_status
            ):
                message = payload.get("error") or payload.get("message") or status or "unknown error"
                raise RuntimeError(f"BFL generation failed: {message}")

            last_status = status or last_status
            time.sleep(_POLL_INTERVAL_SECONDS)

        raise RuntimeError(f"BFL generation timed out while waiting for result (last status: {last_status})")

    def _extract_polling_url(self, submit_payload: dict[str, Any]) -> str:
        polling_url = submit_payload.get("polling_url")
        if isinstance(polling_url, str) and polling_url:
            return polling_url

        request_id = submit_payload.get("id")
        if isinstance(request_id, str) and request_id:
            return f"{self._base_url}{BFL_RESULT_ENDPOINT}?id={request_id}"

        raise RuntimeError("BFL submit response missing polling_url/id")

    @staticmethod
    def _extract_sample_url(result_payload: dict[str, Any]) -> str:
        result = result_payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("BFL result payload missing result object")
        sample = result.get("sample")
        if isinstance(sample, str) and sample:
            return sample
        raise RuntimeError("BFL result payload missing sample url")

    @staticmethod
    def _json_object(payload: object, *, context: str) -> dict[str, Any]:
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
        raise RuntimeError(f"Unexpected BFL {context} response format")

    @staticmethod
    def _to_data_uri(image_bytes: bytes) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"
