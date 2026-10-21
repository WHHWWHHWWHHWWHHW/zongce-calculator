"""可选：后端同时提供前端构建产物（本机演示，一个端口）。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zongce_backend.config import Settings
from zongce_backend.main import create_app


def _dist(tmp_path: Path, *, assets: bool = True) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>index</title>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    if assets:
        (dist / "assets").mkdir()
        (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    return dist


def test_serves_static_files_and_spa_fallback(settings: Settings, tmp_path: Path) -> None:
    app = create_app(settings.model_copy(update={"frontend_dist": _dist(tmp_path)}))
    with TestClient(app) as client:
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/favicon.svg").text == "<svg/>"
        for path in ("/", "/login", "/review/match", "/../secret.txt", "/%2e%2e/secret.txt"):
            response = client.get(path)
            assert response.status_code == 200
            assert "<title>index</title>" in response.text
        assert client.get("/api/v1/health").json()["status"] == "ok"
        missing = client.get("/api/v1/nope")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "http_404"
        assert client.get("/api").status_code == 404
        assert "/{path}" not in client.get("/api/v1/openapi.json").json()["paths"]


def test_dist_without_assets_dir(settings: Settings, tmp_path: Path) -> None:
    app = create_app(settings.model_copy(update={"frontend_dist": _dist(tmp_path, assets=False)}))
    with TestClient(app) as client:
        assert "<title>index</title>" in client.get("/assets/app.js").text


def test_missing_index_is_reported(settings: Settings, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="pnpm build"):
        create_app(settings.model_copy(update={"frontend_dist": tmp_path}))
