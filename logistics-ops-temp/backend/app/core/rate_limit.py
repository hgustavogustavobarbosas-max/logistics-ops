import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError


class RateLimiter:
    """Janela deslizante em memória, por IP e escopo.

    Vale para uma única instância da API. Com várias réplicas, o estado precisa ir
    para um armazenamento compartilhado (ex.: Redis).
    """

    def __init__(self, scope: str, limit: int, window_seconds: int) -> None:
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - hits[0])))
                raise TooManyRequestsError(
                    "Muitas tentativas. Aguarde antes de tentar novamente.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def __call__(self, request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        client = request.client.host if request.client else "unknown"
        self.check(f"{self.scope}:{client}")
