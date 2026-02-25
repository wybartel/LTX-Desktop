"""Unit tests for LTX API client service."""

from __future__ import annotations

import pytest

from services.ltx_api_client.ltx_api_client_impl import LTXAPIClientImpl
from tests.fakes.services import FakeHTTPClient, FakeResponse


def test_generate_text_to_video_returns_binary_content() -> None:
    http = FakeHTTPClient()
    http.queue(
        "post",
        FakeResponse(
            status_code=200,
            headers={"Content-Type": "video/mp4"},
            content=b"video-bytes",
        ),
    )

    client = LTXAPIClientImpl(http=http, ltx_api_base_url="https://api.ltx.video")
    out = client.generate_text_to_video(
        api_key="test-key",
        prompt="A mountain",
        model="ltx-2-pro",
        resolution="1920x1080",
        duration=5.0,
        fps=24.0,
        generate_audio=False,
        camera_motion="dolly_in",
    )

    assert out == b"video-bytes"
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call.url == "https://api.ltx.video/v1/text-to-video"
    assert call.headers == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    assert call.json_payload is not None
    assert call.json_payload["prompt"] == "A mountain"
    assert call.json_payload["resolution"] == "1920x1080"
    assert call.json_payload["camera_motion"] == "dolly_in"


def test_generate_image_to_video_uploads_image_then_downloads_video(tmp_path) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"fake-image")

    http = FakeHTTPClient()
    http.queue(
        "post",
        FakeResponse(
            status_code=200,
            json_payload={
                "upload_url": "https://upload.example.com/path",
                "storage_uri": "storage://image/123",
                "required_headers": {"x-ms-blob-type": "BlockBlob"},
            },
        ),
    )
    http.queue(
        "put",
        FakeResponse(status_code=200),
    )
    http.queue(
        "post",
        FakeResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            json_payload={"video_url": "https://cdn.example.com/output.mp4"},
        ),
    )
    http.queue(
        "get",
        FakeResponse(status_code=200, content=b"downloaded-video"),
    )

    client = LTXAPIClientImpl(http=http, ltx_api_base_url="https://api.ltx.video")
    out = client.generate_image_to_video(
        api_key="test-key",
        prompt="Animate this frame",
        image_path=str(image_path),
        model="ltx-2-pro",
        resolution="1920x1080",
        duration=4.0,
        fps=24.0,
        generate_audio=True,
        camera_motion="jib_up",
    )

    assert out == b"downloaded-video"
    assert len(http.calls) == 4
    assert http.calls[0].url == "https://api.ltx.video/v1/upload"
    assert http.calls[1].method == "put"
    assert http.calls[2].url == "https://api.ltx.video/v1/image-to-video"
    assert http.calls[2].json_payload is not None
    assert http.calls[2].json_payload["image_uri"] == "storage://image/123"
    assert http.calls[2].json_payload["camera_motion"] == "jib_up"
    assert http.calls[3].url == "https://cdn.example.com/output.mp4"


def test_generate_text_to_video_omits_camera_motion_when_none() -> None:
    http = FakeHTTPClient()
    http.queue(
        "post",
        FakeResponse(
            status_code=200,
            headers={"Content-Type": "video/mp4"},
            content=b"video-bytes",
        ),
    )

    client = LTXAPIClientImpl(http=http, ltx_api_base_url="https://api.ltx.video")
    out = client.generate_text_to_video(
        api_key="test-key",
        prompt="A mountain",
        model="ltx-2-pro",
        resolution="1920x1080",
        duration=5.0,
        fps=24.0,
        generate_audio=False,
        camera_motion="none",
    )

    assert out == b"video-bytes"
    call = http.calls[0]
    assert call.json_payload is not None
    assert "camera_motion" not in call.json_payload


def test_generate_text_to_video_raises_on_non_200() -> None:
    http = FakeHTTPClient()
    http.queue(
        "post",
        FakeResponse(
            status_code=401,
            text="unauthorized",
            headers={"Content-Type": "application/json"},
            json_payload={"error": "unauthorized"},
        ),
    )

    client = LTXAPIClientImpl(http=http, ltx_api_base_url="https://api.ltx.video")
    with pytest.raises(RuntimeError, match="401"):
        client.generate_text_to_video(
            api_key="bad-key",
            prompt="A mountain",
            model="ltx-2-pro",
            resolution="1920x1080",
            duration=5.0,
            fps=24.0,
            generate_audio=False,
        )
