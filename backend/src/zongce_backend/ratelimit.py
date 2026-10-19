"""登录失败限流（单进程内存实现，适合本机运行；多进程部署时需换成共享存储）。"""

import math
import time
from collections import deque
from collections.abc import Callable

from .errors import TooManyRequestsError


class LoginLimiter:
    """在滑动时间窗内，按账号、按客户端 IP 分别统计登录失败次数，超过上限即拒绝登录。"""

    def __init__(
        self,
        *,
        max_per_user: int,
        max_per_ip: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self.max_per_user = max_per_user
        self.max_per_ip = max_per_ip
        self.window = window_seconds
        self.clock = clock
        self.max_keys = max_keys
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float]:
        times = self._failures.get(key, deque())
        while times and now - times[0] >= self.window:
            times.popleft()
        return times

    def _blocked_for(self, key: str, limit: int, now: float) -> float:
        times = self._recent(key, now)
        if len(times) < limit:
            return 0.0
        return self.window - (now - times[-limit])

    def check(self, username: str, ip: str) -> None:
        now = self.clock()
        wait = max(
            self._blocked_for(f"user:{username}", self.max_per_user, now),
            self._blocked_for(f"ip:{ip}", self.max_per_ip, now),
        )
        if wait > 0:
            minutes = math.ceil(wait / 60)
            raise TooManyRequestsError(
                f"登录失败次数过多，请 {minutes} 分钟后再试", retry_after=math.ceil(wait)
            )

    def failed(self, username: str, ip: str) -> None:
        now = self.clock()
        if len(self._failures) >= self.max_keys:
            self._prune(now)
        for key in (f"user:{username}", f"ip:{ip}"):
            times = self._recent(key, now)
            times.append(now)
            self._failures[key] = times

    def succeeded(self, username: str) -> None:
        self._failures.pop(f"user:{username}", None)

    def _prune(self, now: float) -> None:
        for key in list(self._failures):
            if not self._recent(key, now):
                del self._failures[key]

    def tracked_keys(self) -> int:
        return len(self._failures)
