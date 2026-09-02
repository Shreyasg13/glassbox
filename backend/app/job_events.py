"""Per-job WebSocket fan-out for /ws/jobs/{job_id}.

Same broadcast pattern as routers/ws.py's ConnectionManager, scoped per
job id instead of one global channel. `finish()` sends the terminal frame
and then closes+drops every socket registered for that job, matching the
envelope contract documented at the bottom of models.py (the socket
closes after the terminal `status` frame).

Phase 6: `publish` sends to every socket registered for a job
concurrently with a per-socket timeout, instead of awaiting each
`send_text` in sequence -- a stalled viewer tab must not delay job
progress frames reaching everyone else watching the same run.
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Optional

from fastapi import WebSocket

SEND_TIMEOUT_SECONDS = 2.0


class JobBroadcaster:
    def __init__(self) -> None:
        self._sockets: Dict[str, List[WebSocket]] = {}

    def register(self, job_id: str, ws: WebSocket) -> None:
        self._sockets.setdefault(job_id, []).append(ws)

    def unregister(self, job_id: str, ws: WebSocket) -> None:
        sockets = self._sockets.get(job_id)
        if not sockets:
            return
        if ws in sockets:
            sockets.remove(ws)
        if not sockets:
            self._sockets.pop(job_id, None)

    async def publish(self, job_id: str, message: dict) -> None:
        sockets = list(self._sockets.get(job_id, []))
        if not sockets:
            return
        payload = json.dumps(message)

        async def _send(ws: WebSocket) -> Optional[WebSocket]:
            try:
                await asyncio.wait_for(ws.send_text(payload), timeout=SEND_TIMEOUT_SECONDS)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*(_send(ws) for ws in sockets))
        for stale in results:
            if stale is not None:
                self.unregister(job_id, stale)

    async def finish(self, job_id: str, message: dict) -> None:
        await self.publish(job_id, message)
        sockets = self._sockets.pop(job_id, [])
        for ws in sockets:
            try:
                await asyncio.wait_for(ws.close(), timeout=SEND_TIMEOUT_SECONDS)
            except Exception:
                pass


broadcaster = JobBroadcaster()
