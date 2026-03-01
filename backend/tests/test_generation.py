"""Integration-style tests for generation and image endpoints."""

from __future__ import annotations

from pathlib import Path

from state.app_state_types import GpuSlot, VideoPipelineState, VideoPipelineWarmth
from tests.fakes.services import FakeFastVideoPipeline

_T2V_JSON = {
    "prompt": "test",
    "resolution": "540p",
    "model": "fast",
    "duration": "2",
    "fps": "24",
}


def _enable_local_text_encoding(test_state) -> None:
    test_state.state.app_settings.use_local_text_encoder = True


def _fake_running_generation_state(test_state) -> None:
    pipeline = FakeFastVideoPipeline()
    test_state.state.gpu_slot = GpuSlot(
        active_pipeline=VideoPipelineState(
            pipeline=pipeline,
            warmth=VideoPipelineWarmth.COLD,
            is_compiled=False,
        ),
        generation=None,
    )
    test_state.generation.start_generation("running")


class TestGenerate:
    def test_t2v_happy_path(self, client, test_state, fake_services, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A beautiful sunset",
                "resolution": "1080p",
                "model": "fast",
                "duration": "2",
                "fps": "24",
                "cameraMotion": "none",
            },
        )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert data["video_path"] is not None
        assert Path(data["video_path"]).exists()

        pipeline = fake_services.fast_video_pipeline
        assert len(pipeline.generate_calls) == 1

    def test_already_running(self, client, test_state):
        _fake_running_generation_state(test_state)

        r = client.post("/api/generate", json=_T2V_JSON)
        assert r.status_code == 409

    def test_i2v_nonexistent_image(self, client, test_state, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)

        r = client.post(
            "/api/generate",
            json={**_T2V_JSON, "imagePath": "/no/such/file.png"},
        )
        assert r.status_code == 400

    def test_resolution_mapping_540p(self, client, test_state, fake_services, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)

        r = client.post("/api/generate", json=_T2V_JSON)
        assert r.status_code == 200

        pipeline = fake_services.fast_native_video_pipeline
        call = pipeline.generate_calls[0]
        assert call["width"] == 960
        assert call["height"] == 512

    def test_resolution_mapping_720p(self, client, test_state, fake_services, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)

        r = client.post("/api/generate", json={**_T2V_JSON, "resolution": "720p"})
        assert r.status_code == 200

        pipeline = fake_services.fast_native_video_pipeline
        call = pipeline.generate_calls[0]
        assert call["width"] == 1280
        assert call["height"] == 704

    def test_locked_seed(self, client, test_state, fake_services, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)
        test_state.state.app_settings.seed_locked = True
        test_state.state.app_settings.locked_seed = 123

        r = client.post("/api/generate", json=_T2V_JSON)
        assert r.status_code == 200

        pipeline = fake_services.fast_native_video_pipeline
        assert pipeline.generate_calls[0]["seed"] == 123

    def test_error_sets_generation_error(self, client, test_state, fake_services, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)
        fake_services.fast_native_video_pipeline.raise_on_generate = RuntimeError("GPU OOM")

        r = client.post("/api/generate", json=_T2V_JSON)
        assert r.status_code == 500

        progress = test_state.generation.get_generation_progress()
        assert progress.status == "error"

    def test_cancelled_response(self, client, test_state, fake_services, create_fake_model_files):
        create_fake_model_files()
        _enable_local_text_encoding(test_state)
        fake_services.fast_native_video_pipeline.raise_on_generate = RuntimeError("cancelled")

        r = client.post("/api/generate", json=_T2V_JSON)
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


class TestForcedApiGenerate:
    def test_t2v_routes_to_ltx_api(self, client, test_state, fake_services):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A mountain lake",
                "resolution": "1080p",
                "model": "fast",
                "duration": "6",
                "fps": "50",
                "audio": "true",
                "cameraMotion": "dolly_in",
            },
        )

        assert r.status_code == 200
        assert r.json()["status"] == "complete"
        assert len(fake_services.ltx_api_client.text_to_video_calls) == 1
        call = fake_services.ltx_api_client.text_to_video_calls[0]
        assert call["model"] == "ltx-2-3-fast"
        assert call["resolution"] == "1920x1080"
        assert call["duration"] == 6.0
        assert call["fps"] == 50.0
        assert call["generate_audio"] is True
        assert call["camera_motion"] == "dolly_in"

    def test_i2v_routes_to_ltx_api(self, client, test_state, fake_services, make_test_image, tmp_path):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"
        image_path = tmp_path / "input.png"
        image_path.write_bytes(make_test_image().getvalue())

        r = client.post(
            "/api/generate",
            json={
                "prompt": "Animate this frame",
                "resolution": "2160p",
                "model": "pro",
                "duration": "8",
                "fps": "25",
                "audio": "false",
                "cameraMotion": "jib_up",
                "imagePath": str(image_path),
            },
        )

        assert r.status_code == 200
        assert r.json()["status"] == "complete"
        assert len(fake_services.ltx_api_client.image_to_video_calls) == 1
        call = fake_services.ltx_api_client.image_to_video_calls[0]
        assert call["model"] == "ltx-2-3-pro"
        assert call["resolution"] == "3840x2160"
        assert call["duration"] == 8.0
        assert call["fps"] == 25.0
        assert call["camera_motion"] == "jib_up"

    def test_camera_motion_none_maps_to_none_for_t2v(self, client, test_state, fake_services):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A mountain lake",
                "resolution": "1080p",
                "model": "fast",
                "duration": "6",
                "fps": "50",
                "audio": "true",
                "cameraMotion": "none",
            },
        )

        assert r.status_code == 200
        assert len(fake_services.ltx_api_client.text_to_video_calls) == 1
        call = fake_services.ltx_api_client.text_to_video_calls[0]
        assert call["camera_motion"] == "none"

    def test_camera_motion_none_maps_to_none_for_i2v(self, client, test_state, fake_services, make_test_image, tmp_path):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"
        image_path = tmp_path / "input-none.png"
        image_path.write_bytes(make_test_image().getvalue())

        r = client.post(
            "/api/generate",
            json={
                "prompt": "Animate this frame",
                "resolution": "2160p",
                "model": "pro",
                "duration": "8",
                "fps": "25",
                "audio": "false",
                "cameraMotion": "none",
                "imagePath": str(image_path),
            },
        )

        assert r.status_code == 200
        assert len(fake_services.ltx_api_client.image_to_video_calls) == 1
        call = fake_services.ltx_api_client.image_to_video_calls[0]
        assert call["camera_motion"] == "none"

    def test_i2v_fast_routes_to_fast_model(self, client, test_state, fake_services, make_test_image, tmp_path):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"
        image_path = tmp_path / "input-fast.png"
        image_path.write_bytes(make_test_image().getvalue())

        r = client.post(
            "/api/generate",
            json={
                "prompt": "Animate this frame quickly",
                "resolution": "1080p",
                "model": "fast",
                "duration": "6",
                "fps": "25",
                "audio": "false",
                "imagePath": str(image_path),
            },
        )

        assert r.status_code == 200
        assert r.json()["status"] == "complete"
        assert len(fake_services.ltx_api_client.image_to_video_calls) == 1
        call = fake_services.ltx_api_client.image_to_video_calls[0]
        assert call["model"] == "ltx-2-3-fast"
        assert call["resolution"] == "1920x1080"
        assert call["duration"] == 6.0
        assert call["fps"] == 25.0

    def test_invalid_forced_model_rejected(self, client, test_state):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A city skyline",
                "resolution": "1080p",
                "model": "ultra",
                "duration": "6",
                "fps": "25",
                "audio": "false",
            },
        )

        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_FORCED_API_MODEL"

    def test_missing_api_key_returns_integrity_error(self, client, test_state):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = ""

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A city skyline",
                "resolution": "1080p",
                "model": "pro",
                "duration": "6",
                "fps": "25",
                "audio": "false",
            },
        )

        assert r.status_code == 400
        assert r.json()["error"] == "PRO_API_KEY_REQUIRED"

    def test_invalid_forced_resolution_rejected(self, client, test_state):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A city skyline",
                "resolution": "720p",
                "model": "pro",
                "duration": "6",
                "fps": "25",
                "audio": "false",
            },
        )

        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_FORCED_API_RESOLUTION"

    def test_invalid_forced_duration_rejected(self, client, test_state):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A city skyline",
                "resolution": "1080p",
                "model": "pro",
                "duration": "5",
                "fps": "25",
                "audio": "false",
            },
        )

        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_FORCED_API_DURATION"

    def test_invalid_forced_fps_rejected(self, client, test_state):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A city skyline",
                "resolution": "1080p",
                "model": "pro",
                "duration": "6",
                "fps": "24",
                "audio": "false",
            },
        )

        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_FORCED_API_FPS"

    def test_invalid_camera_motion_rejected_with_422(self, client, test_state):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A city skyline",
                "resolution": "1080p",
                "model": "pro",
                "duration": "6",
                "fps": "25",
                "audio": "false",
                "cameraMotion": "orbit",
            },
        )

        assert r.status_code == 422

    def test_forced_api_cancelled_response(self, client, test_state, fake_services):
        test_state.config.force_api_generations = True
        test_state.state.app_settings.ltx_api_key = "api-key"
        fake_services.ltx_api_client.raise_on_text_to_video = RuntimeError("cancelled")

        r = client.post(
            "/api/generate",
            json={
                "prompt": "A mountain lake",
                "resolution": "1080p",
                "model": "pro",
                "duration": "6",
                "fps": "25",
                "audio": "false",
            },
        )

        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


class TestGenerateCancel:
    def test_cancel_active(self, client, test_state):
        _fake_running_generation_state(test_state)

        r = client.post("/api/generate/cancel")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cancelling"

    def test_cancel_no_active(self, client):
        r = client.post("/api/generate/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "no_active_generation"


class TestGenerationProgress:
    def test_idle(self, client):
        r = client.get("/api/generation/progress")
        assert r.status_code == 200
        assert r.json()["status"] == "idle"

    def test_running(self, client, test_state):
        _fake_running_generation_state(test_state)
        test_state.generation.update_progress("inference", 50, 4, 8)

        r = client.get("/api/generation/progress")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"
        assert data["phase"] == "inference"
        assert data["progress"] == 50
        assert data["currentStep"] == 4
        assert data["totalSteps"] == 8

    def test_running_from_api_generation_state(self, client, test_state):
        test_state.generation.start_api_generation("api-running")
        test_state.generation.update_progress("inference", 35)

        r = client.get("/api/generation/progress")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"
        assert data["phase"] == "inference"
        assert data["progress"] == 35
        assert data["currentStep"] is None
        assert data["totalSteps"] is None


class TestGenerateImage:
    def test_happy_path(self, client):
        r = client.post(
            "/api/generate-image",
            json={"prompt": "A cat", "width": 1024, "height": 1024, "numSteps": 4},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert len(data["image_paths"]) == 1
        assert Path(data["image_paths"][0]).exists()

    def test_dimension_clamping(self, client, fake_services):
        r = client.post(
            "/api/generate-image",
            json={"prompt": "test", "width": 1023, "height": 1023},
        )
        assert r.status_code == 200

        call = fake_services.image_generation_pipeline.generate_calls[0]
        assert call["width"] == 1008
        assert call["height"] == 1008

    def test_num_images_clamped(self, client, fake_services):
        r = client.post(
            "/api/generate-image",
            json={"prompt": "test", "numImages": 20},
        )
        assert r.status_code == 200

        assert len(fake_services.image_generation_pipeline.generate_calls) == 12

    def test_error(self, client, fake_services):
        fake_services.image_generation_pipeline.raise_on_generate = RuntimeError("GPU OOM")

        r = client.post("/api/generate-image", json={"prompt": "test"})
        assert r.status_code == 500

    def test_cancelled(self, client, fake_services):
        fake_services.image_generation_pipeline.raise_on_generate = RuntimeError("cancelled")

        r = client.post("/api/generate-image", json={"prompt": "test"})
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


class TestForcedApiGenerateImage:
    def test_generate_image_routes_to_flux_api(self, client, test_state, fake_services):
        test_state.config.force_api_generations = True

        r = client.post(
            "/api/generate-image",
            json={"prompt": "A cat", "width": 1024, "height": 1024, "numSteps": 4, "numImages": 2},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert len(data["image_paths"]) == 2
        assert len(fake_services.flux_api_client.text_to_image_calls) == 2
        assert len(fake_services.image_generation_pipeline.generate_calls) == 0

    def test_generate_image_missing_bfl_key(self, client, test_state, fake_services):
        test_state.config.force_api_generations = True
        fake_services.flux_api_client.configured = False

        r = client.post("/api/generate-image", json={"prompt": "A cat"})

        assert r.status_code == 500
        assert r.json()["error"] == "BFL_API_KEY_NOT_CONFIGURED"

    def test_generate_image_cancelled(self, client, test_state, fake_services):
        test_state.config.force_api_generations = True
        fake_services.flux_api_client.raise_on_text_to_image = RuntimeError("cancelled")

        r = client.post("/api/generate-image", json={"prompt": "A cat"})

        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_edit_image_routes_to_flux_api(self, client, test_state, fake_services, make_test_image):
        test_state.config.force_api_generations = True

        r = client.post(
            "/api/edit-image",
            data={"prompt": "Make it blue", "width": "1024", "height": "1024"},
            files={"image": ("img1.png", make_test_image(100, 100), "image/png")},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert len(data["image_paths"]) == 1
        assert len(fake_services.flux_api_client.image_edit_calls) == 1
        assert len(fake_services.image_generation_pipeline.generate_edit_calls) == 0

    def test_edit_image_rejects_more_than_four_refs(self, client, test_state, make_test_image):
        test_state.config.force_api_generations = True

        r = client.post(
            "/api/edit-image",
            data={"prompt": "Combine styles", "width": "1024", "height": "1024"},
            files={
                "image": ("img1.png", make_test_image(100, 100), "image/png"),
                "image2": ("img2.png", make_test_image(100, 100), "image/png"),
                "image3": ("img3.png", make_test_image(100, 100), "image/png"),
                "image4": ("img4.png", make_test_image(100, 100), "image/png"),
                "image5": ("img5.png", make_test_image(100, 100), "image/png"),
            },
        )

        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_KLEIN_REFERENCE_COUNT"


class TestEmptyPromptRejected:
    def test_empty_prompt_rejected(self, client):
        r = client.post("/api/generate", json={"prompt": ""})
        assert r.status_code == 422

    def test_whitespace_prompt_rejected(self, client):
        r = client.post("/api/generate", json={"prompt": "   "})
        assert r.status_code == 422

    def test_missing_prompt_rejected(self, client):
        r = client.post("/api/generate", json={})
        assert r.status_code == 422

    def test_empty_image_prompt_rejected(self, client):
        r = client.post("/api/generate-image", json={"prompt": ""})
        assert r.status_code == 422

    def test_whitespace_image_prompt_rejected(self, client):
        r = client.post("/api/generate-image", json={"prompt": "   "})
        assert r.status_code == 422

    def test_missing_image_prompt_rejected(self, client):
        r = client.post("/api/generate-image", json={})
        assert r.status_code == 422


class TestEditImage:
    def test_happy_path(self, client, make_test_image):
        img_buf = make_test_image(100, 100)

        r = client.post(
            "/api/edit-image",
            data={"prompt": "Make it blue", "width": "1024", "height": "1024"},
            files={"image": ("test.png", img_buf, "image/png")},
        )
        assert r.status_code == 200

        data = r.json()
        assert data["status"] == "complete"
        assert len(data["image_paths"]) == 1
        assert Path(data["image_paths"][0]).exists()

    def test_no_image(self, client):
        r = client.post(
            "/api/edit-image",
            data={"prompt": "Make it blue", "width": "1024", "height": "1024"},
        )
        assert r.status_code == 422

    def test_multiple_reference_images(self, client, fake_services, make_test_image):
        r = client.post(
            "/api/edit-image",
            data={"prompt": "Combine styles", "width": "1024", "height": "1024"},
            files={
                "image": ("img1.png", make_test_image(100, 100), "image/png"),
                "image2": ("img2.png", make_test_image(100, 100), "image/png"),
                "image3": ("img3.png", make_test_image(100, 100), "image/png"),
            },
        )
        assert r.status_code == 200

        call = fake_services.image_generation_pipeline.generate_edit_calls[0]
        assert isinstance(call["image"], list)
        assert len(call["image"]) == 3
