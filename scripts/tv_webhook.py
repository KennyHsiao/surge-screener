#!/usr/bin/env python3
"""TradingView alert webhook receiver (environment scaffold).

TradingView has no public data API, but Pro+ alerts can POST a JSON payload to a
webhook URL when a Pine Script / indicator condition fires. This is the only
*supported* way to get signals out of TradingView. This script is the receiving
end: a tiny, dependency-free HTTP server that validates a shared secret, stores
each signal, and logs it. Wiring the stored signals into the screener / IBKR
execution is a later step -- this just gets the plumbing ready.

Uses only the Python standard library (no Flask/FastAPI) so it adds no
dependencies to the project.

Run locally:
    export TV_WEBHOOK_SECRET="pick-a-long-random-string"
    python scripts/tv_webhook.py --port 8000

Expose to the internet so TradingView can reach it (TradingView only POSTs to
public HTTPS/HTTP endpoints, not localhost):
    ngrok http 8000           # or: cloudflared tunnel --url http://localhost:8000
Then in TradingView: Alert > Notifications > Webhook URL = https://<tunnel>/tv
with this alert message (Pine placeholders fill at fire time):
    {
      "secret": "pick-a-long-random-string",
      "ticker": "{{ticker}}",
      "action": "{{strategy.order.action}}",
      "price": {{close}},
      "time": "{{timenow}}",
      "note": "{{strategy.order.comment}}"
    }

Stored signals land in content/tv_signals.json (newest last), the same content/
dir the dashboard already reads from.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_STORE = Path(__file__).resolve().parent.parent / "content" / "tv_signals.json"
_MAX_BODY = 64 * 1024  # reject absurd payloads


def _append_signal(payload: dict) -> None:
    """Append one signal to the JSON store (best-effort, atomic write)."""
    record = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "ticker": str(payload.get("ticker", "")).upper(),
        "action": payload.get("action"),
        "price": payload.get("price"),
        "time": payload.get("time"),
        "note": payload.get("note"),
        "raw": payload,
    }
    try:
        existing = []
        if _STORE.is_file():
            existing = json.loads(_STORE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        existing.append(record)
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, _STORE)
    except Exception as e:
        print(f"[tv_webhook] store error: {e}")


class _Handler(BaseHTTPRequestHandler):
    # Quieter default logging.
    def log_message(self, fmt, *args):  # noqa: N802
        print(f"[tv_webhook] {self.address_string()} {fmt % args}")

    def _reply(self, code: int, msg: str) -> None:
        body = json.dumps({"ok": code < 400, "msg": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802  -- health check
        if self.path in ("/", "/health"):
            self._reply(200, "tv_webhook up")
        else:
            self._reply(404, "not found")

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") not in ("/tv", "/webhook", ""):
            self._reply(404, "unknown path")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY:
            self._reply(400, "bad content length")
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload not an object")
        except Exception:
            self._reply(400, "invalid json")
            return

        secret = os.environ.get("TV_WEBHOOK_SECRET", "")
        if not secret:
            self._reply(503, "server has no TV_WEBHOOK_SECRET configured")
            return
        # constant-time compare to avoid leaking the secret via timing
        if not hmac.compare_digest(str(payload.get("secret", "")), secret):
            self._reply(401, "bad secret")
            return

        _append_signal(payload)
        print(f"[tv_webhook] stored signal: "
              f"{payload.get('ticker')} {payload.get('action')} "
              f"@ {payload.get('price')}")
        self._reply(200, "stored")


def main() -> int:
    ap = argparse.ArgumentParser(description="TradingView webhook receiver")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if not os.environ.get("TV_WEBHOOK_SECRET"):
        print("WARNING: TV_WEBHOOK_SECRET is not set — all POSTs will be "
              "rejected with 503 until you export one.")
    print(f"[tv_webhook] listening on {args.host}:{args.port} "
          f"(POST /tv, GET /health). Store: {_STORE}")
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[tv_webhook] shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
