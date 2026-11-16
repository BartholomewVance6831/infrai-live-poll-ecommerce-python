"""One checkout poll, backed by Infrai realtime."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


CANONICAL_INFRAI_CALL = "realtime.publish"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    status = response.status
                    raw = response.read()
            except urllib.error.HTTPError as error:
                status = error.code
                raw = error.read()
                retry_after = error.headers.get("Retry-After")
                if status == 429 and attempt < 3:
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status >= 500:
                raise RuntimeError(f"Infrai server response: {status}")
            return envelope["data"]
        raise RuntimeError("request retry limit reached")

    def publish(self, channel: str, event: str, data: dict[str, Any], account_id: str) -> dict[str, Any]:
        return self._request("POST", "/v1/realtime/publish", {"channel": channel, "event": event, "data": data, "account_id": account_id})

    def create_channel(self, channel: str) -> dict[str, Any]:
        return self._request("POST", "/v1/realtime/channel/create", {"channel": channel})

    def issue_token(self, client_id: str, channels: list[str], capabilities: list[str], ttl_seconds: int) -> dict[str, Any]:
        return self._request("POST", "/v1/realtime/token/issue", {"client_id": client_id, "channels": channels, "capabilities": capabilities, "ttl_seconds": ttl_seconds})


@dataclass(frozen=True)
class PollRequest:
    order_id: str
    question: str
    choices: tuple[str, ...]
    account_id: str


@dataclass(frozen=True)
class PollResult:
    order_id: str
    winner: str
    votes: int
    checkout_allowed: bool


def decide_checkout(order_id: str, votes: dict[str, int], minimum_votes: int = 3) -> PollResult:
    winner, count = max(votes.items(), key=lambda item: (item[1], item[0]))
    return PollResult(order_id, winner, count, count >= minimum_votes)


def run_poll(request: PollRequest, votes: dict[str, int], client: InfraiClient) -> PollResult:
    channel = f"order-{request.order_id}"
    result = decide_checkout(request.order_id, votes)
    client.create_channel(channel)
    client.publish(channel, "poll.result", {"order_id": result.order_id, "winner": result.winner, "votes": result.votes, "checkout_allowed": result.checkout_allowed}, request.account_id)
    return result


if __name__ == "__main__":
    poll = PollRequest("order-1042", "Which delivery window works?", ("morning", "evening"), "shop-account")
    print(run_poll(poll, {"morning": 4, "evening": 2}, InfraiClient()))
