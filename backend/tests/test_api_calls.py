"""Integration-style tests for /api/suggest-gap-prompt, /api/retake."""

from __future__ import annotations

import uuid

from services.interfaces import HttpTimeoutError
from services.ltx_api_client.ltx_api_client import LTXAPIClientError, LTXRetakeResult
from tests.fakes import FakeResponse


def _gemini_ok(text: str = "Enhanced prompt text") -> FakeResponse:
    return FakeResponse(
        status_code=200,
        json_payload={"candidates": [{"content": {"parts": [{"text": text}]}}]},
    )


def _gemini_error(status: int = 429, body: str = "rate limited") -> FakeResponse:
    return FakeResponse(status_code=status, text=body)


def _gemini_empty_candidates() -> FakeResponse:
    return FakeResponse(status_code=200, json_payload={"candidates": []})


class TestSuggestGapPrompt:
    def test_happy_path_with_prompts(self, client, test_state):
        test_state.state.app_settings.gemini_api_key = "key"
        test_state.http.queue("post", _gemini_ok("A smooth transition scene"))

        r = client.post(
            "/api/suggest-gap-prompt",
            json={"beforePrompt": "sunset on a beach", "afterPrompt": "sunrise over mountains", "gapDuration": 3},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["suggested_prompt"] == "A smooth transition scene"

    def test_happy_path_with_frames(self, client, test_state, make_test_image, tmp_path):
        test_state.state.app_settings.gemini_api_key = "key"
        test_state.http.queue("post", _gemini_ok("Transition clip"))

        before_path = tmp_path / "before.png"
        after_path = tmp_path / "after.png"
        before_path.write_bytes(make_test_image().getvalue())
        after_path.write_bytes(make_test_image().getvalue())

        r = client.post(
            "/api/suggest-gap-prompt",
            json={"beforeFrame": str(before_path), "afterFrame": str(after_path)},
        )
        assert r.status_code == 200

        user_parts = test_state.http.calls[-1].json_payload["contents"][0]["parts"]
        inline_parts = [part for part in user_parts if "inlineData" in part]
        assert len(inline_parts) == 2

    def test_no_context_400(self, client, test_state):
        test_state.state.app_settings.gemini_api_key = "key"
        r = client.post("/api/suggest-gap-prompt", json={})
        assert r.status_code == 400

    def test_missing_gemini_key_400(self, client):
        r = client.post("/api/suggest-gap-prompt", json={"beforePrompt": "test"})
        assert r.status_code == 400
        assert r.json()["error"] == "GEMINI_API_KEY_MISSING"

    def test_timeout_504(self, client, test_state):
        test_state.state.app_settings.gemini_api_key = "key"
        test_state.http.queue("post", HttpTimeoutError("timeout"))

        r = client.post("/api/suggest-gap-prompt", json={"beforePrompt": "test"})
        assert r.status_code == 504


class TestRetake:
    def _make_video(self, test_state) -> str:
        video_file = test_state.config.outputs_dir / f"retake_input_{uuid.uuid4().hex[:6]}.mp4"
        video_file.write_bytes(b"\x00" * 2048)
        return str(video_file)

    def _base_payload(self, video_path: str) -> dict[str, object]:
        return {
            "video_path": video_path,
            "start_time": 1.0,
            "duration": 3.0,
            "prompt": "make it dramatic",
        }

    def test_happy_path_binary_response(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)
        test_state.ltx_api_client.retake_result = LTXRetakeResult(
            video_bytes=b"\x00\x00\x00\x1cftypisom" + b"\x00" * 500,
            result_payload=None,
        )

        r = client.post("/api/retake", json=self._base_payload(video_path))
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert data["video_path"]

    def test_happy_path_json_video_url(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)
        test_state.ltx_api_client.retake_result = LTXRetakeResult(
            video_bytes=b"\x00\x00\x00\x1cftypisom" + b"\x00" * 500,
            result_payload=None,
        )

        r = client.post("/api/retake", json=self._base_payload(video_path))
        assert r.status_code == 200
        assert r.json()["status"] == "complete"

    def test_duration_too_short(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)

        r = client.post("/api/retake", json={"video_path": video_path, "start_time": 0, "duration": 1})
        assert r.status_code == 400

    def test_video_not_found(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        r = client.post("/api/retake", json={"video_path": "/nonexistent/video.mp4", "start_time": 0, "duration": 3})
        assert r.status_code == 400

    def test_no_api_key(self, client, test_state):
        video_path = self._make_video(test_state)
        r = client.post("/api/retake", json=self._base_payload(video_path))
        assert r.status_code == 400

    def test_upload_url_failure(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)
        test_state.ltx_api_client.raise_on_retake = LTXAPIClientError(401, "Failed to get upload URL: Unauthorized")

        r = client.post("/api/retake", json=self._base_payload(video_path))
        assert r.status_code == 401

    def test_video_upload_failure(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)
        test_state.ltx_api_client.raise_on_retake = LTXAPIClientError(500, "Video upload failed: Storage error")

        r = client.post("/api/retake", json=self._base_payload(video_path))
        assert r.status_code == 500

    def test_retake_api_422_safety_filter(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)
        test_state.ltx_api_client.raise_on_retake = LTXAPIClientError(422, "Content rejected by safety filters")

        r = client.post("/api/retake", json=self._base_payload(video_path))
        assert r.status_code == 422

    def test_prompt_and_mode_forwarded(self, client, test_state):
        test_state.state.app_settings.ltx_api_key = "test-key"
        video_path = self._make_video(test_state)
        test_state.ltx_api_client.retake_result = LTXRetakeResult(
            video_bytes=b"\x00\x00\x00\x1cftypisom" + b"\x00" * 500,
            result_payload=None,
        )

        client.post(
            "/api/retake",
            json={
                "video_path": video_path,
                "start_time": 2.0,
                "duration": 4.0,
                "prompt": "epic explosion",
                "mode": "replace_video_only",
            },
        )

        retake_call = test_state.ltx_api_client.retake_calls[-1]
        assert retake_call["prompt"] == "epic explosion"
        assert retake_call["mode"] == "replace_video_only"
