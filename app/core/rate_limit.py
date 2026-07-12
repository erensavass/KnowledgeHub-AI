import hashlib
import math
from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError

from app.core.logging import get_logger

logger = get_logger(__name__)

RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int


class RedisRateLimiter:
    def __init__(self, client: Redis, window_seconds: int, fail_open: bool) -> None:
        self.client = client
        self.window_seconds = window_seconds
        self.fail_open = fail_open

    def check(self, scope: str, principal: str, limit: int) -> RateLimitDecision:
        digest = hashlib.sha256(principal.encode()).hexdigest()
        key = f"knowledgehub:rate:{scope}:{digest}"
        try:
            current, ttl = self.client.eval(
                RATE_LIMIT_SCRIPT, 1, key, self.window_seconds
            )
            retry_after = max(1, math.ceil(float(ttl)))
            return RateLimitDecision(int(current) <= limit, retry_after)
        except RedisError:
            logger.warning(
                "rate_limit_backend_unavailable",
                extra={"error_category": "dependency", "scope": scope},
            )
            return RateLimitDecision(self.fail_open, self.window_seconds)
