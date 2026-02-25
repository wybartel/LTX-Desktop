"""LTX API client implementation."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, cast

from services.http_client.http_client import HTTPClient
from services.services_utils import JSONValue


class LTXAPIClientImpl:
    def __init__(self, http: HTTPClient, ltx_api_base_url: str) -> None:
        self._http = http
        self._base_url = ltx_api_base_url.rstrip("/")

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
    ) -> bytes:
        payload: dict[str, JSONValue] = {
            "prompt": prompt,
            "model": model,
            "resolution": resolution,
            "duration": duration,
            "fps": fps,
            "generate_audio": generate_audio,
        }
        response = self._http.post(
            f"{self._base_url}/v1/text-to-video",
            headers=self._json_headers(api_key),
            json_payload=payload,
            timeout=1200,
        )
        return self._extract_video_bytes(response, api_key)

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
    ) -> bytes:
        image_uri = self._upload_image(image_path=image_path, api_key=api_key)
        payload: dict[str, JSONValue] = {
            "prompt": prompt,
            "image_uri": image_uri,
            "model": model,
            "resolution": resolution,
            "duration": duration,
            "fps": fps,
            "generate_audio": generate_audio,
        }
        response = self._http.post(
            f"{self._base_url}/v1/image-to-video",
            headers=self._json_headers(api_key),
            json_payload=payload,
            timeout=1200,
        )
        return self._extract_video_bytes(response, api_key)

    def _upload_image(self, *, image_path: str, api_key: str) -> str:
        upload_resp = self._http.post(
            f"{self._base_url}/v1/upload",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        if upload_resp.status_code != 200:
            err = upload_resp.text[:500]
            raise RuntimeError(f"LTX upload init failed ({upload_resp.status_code}): {err}")

        try:
            payload = cast(dict[str, Any], upload_resp.json())
            upload_url = str(payload["upload_url"])
            storage_uri = str(payload["storage_uri"])
            required_headers = cast(dict[str, str], payload.get("required_headers", {}))
        except Exception as exc:
            raise RuntimeError("Unexpected LTX upload response format") from exc

        path_obj = Path(image_path)
        mime = mimetypes.guess_type(path_obj.name)[0] or "application/octet-stream"
        with open(path_obj, "rb") as image_file:
            put_resp = self._http.put(
                upload_url,
                data=image_file,
                headers={"Content-Type": mime, **required_headers},
                timeout=300,
            )
        if put_resp.status_code not in (200, 201):
            err = put_resp.text[:500]
            raise RuntimeError(f"LTX upload failed ({put_resp.status_code}): {err}")

        return storage_uri

    def _extract_video_bytes(self, response: Any, api_key: str) -> bytes:
        if response.status_code != 200:
            err = response.text[:500] if response.text else "Unknown error"
            raise RuntimeError(f"LTX API generation failed ({response.status_code}): {err}")

        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "video" in content_type or "octet-stream" in content_type:
            if not response.content:
                raise RuntimeError("LTX API returned empty video body")
            return response.content

        try:
            payload = cast(dict[str, Any], response.json())
        except Exception as exc:
            raise RuntimeError("Unexpected LTX API response format") from exc

        video_url = self._extract_video_url(payload)
        if video_url is not None:
            dl_resp = self._http.get(
                video_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=120,
            )
            if dl_resp.status_code != 200:
                raise RuntimeError(f"Failed to download generated video ({dl_resp.status_code})")
            if not dl_resp.content:
                raise RuntimeError("Downloaded generated video is empty")
            return dl_resp.content

        error_text = payload.get("error") or payload.get("message") or payload.get("detail")
        if isinstance(error_text, str) and error_text:
            raise RuntimeError(f"LTX API returned an error payload: {error_text}")
        raise RuntimeError("LTX API response did not include a video payload")

    @staticmethod
    def _extract_video_url(payload: dict[str, Any]) -> str | None:
        direct_keys = ("video_url", "output_video", "output_video_url", "output_url", "url")
        for key in direct_keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value

        nested = payload.get("result")
        if isinstance(nested, dict):
            nested_payload = cast(dict[str, Any], nested)
            for key in direct_keys:
                value = nested_payload.get(key)
                if isinstance(value, str) and value:
                    return value
        return None

    @staticmethod
    def _json_headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
