from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class CooldownService:
    cooldown_seconds: int = 3
    _last_seen: dict[int, datetime] = field(default_factory=dict)

    def allow(self, user_id: int) -> bool:
        now = datetime.now(timezone.utc)
        last = self._last_seen.get(user_id)
        self._last_seen[user_id] = now
        if last is None:
            return True
        return now - last >= timedelta(seconds=self.cooldown_seconds)
