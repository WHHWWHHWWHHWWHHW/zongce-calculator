"""登录失败限流：防止暴力破解密码。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend_helpers import API, PASSWORD, make_user
from zongce_backend.errors import TooManyRequestsError
from zongce_backend.models import Role
from zongce_backend.ratelimit import LoginLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_user_and_ip_windows() -> None:
    clock = FakeClock()
    limiter = LoginLimiter(max_per_user=3, max_per_ip=5, window_seconds=60, clock=clock)
    for _ in range(3):
        limiter.check("u1", "1.1.1.1")
        limiter.failed("u1", "1.1.1.1")
    with pytest.raises(TooManyRequestsError) as caught:
        limiter.check("u1", "9.9.9.9")  # 换 IP 也不行：按账号锁定
    assert caught.value.retry_after == 60
    clock.now += 30
    with pytest.raises(TooManyRequestsError) as caught:
        limiter.check("u1", "1.1.1.1")
    assert caught.value.retry_after == 30
    clock.now += 30  # 窗口过去后恢复
    limiter.check("u1", "1.1.1.1")

    for name in ("a", "b", "c", "d", "e"):  # 同一 IP 换着账号试
        limiter.failed(name, "2.2.2.2")
    with pytest.raises(TooManyRequestsError):
        limiter.check("f", "2.2.2.2")
    limiter.check("f", "3.3.3.3")


def test_success_resets_user_counter() -> None:
    limiter = LoginLimiter(max_per_user=2, max_per_ip=100, window_seconds=60, clock=FakeClock())
    limiter.failed("u", "ip")
    limiter.succeeded("u")
    limiter.failed("u", "ip")
    limiter.check("u", "ip")  # 只剩 1 次失败，未达上限


def test_limiter_prunes_stale_keys() -> None:
    clock = FakeClock()
    limiter = LoginLimiter(max_per_user=5, max_per_ip=5, window_seconds=10, clock=clock, max_keys=4)
    for i in range(3):
        limiter.failed(f"user{i}", f"ip{i}")
    clock.now += 11
    limiter.failed("late", "ip-late")  # 超过 max_keys 时清理过期记录
    assert limiter.tracked_keys() == 2


def test_login_endpoint_locks_after_failures(client: TestClient, app: FastAPI, db: Session) -> None:
    make_user(db, "TEST7001", Role.STUDENT)
    body = {"username": "TEST7001", "password": "wrong-password"}
    for _ in range(app.state.settings.login_max_failures):
        assert client.post(f"{API}/auth/login", json=body).status_code == 401
    locked = client.post(f"{API}/auth/login", json={**body, "password": PASSWORD})
    assert locked.status_code == 429  # 锁定期间即使密码正确也拒绝
    assert locked.json()["error"]["code"] == "too_many_requests"
    assert int(locked.headers["retry-after"]) > 0
    # 其他账号不受影响
    make_user(db, "TEST7002", Role.STUDENT)
    ok = client.post(f"{API}/auth/login", json={"username": "TEST7002", "password": PASSWORD})
    assert ok.status_code == 200
