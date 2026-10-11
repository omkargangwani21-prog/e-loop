"""Local development server: runs the exact same app as Lambda, with no AWS account needed.

    python -m eloop.devserver            # listens on 127.0.0.1:8787

Never expose this to a network: it is single-purpose tooling, not a production server.
"""

from __future__ import annotations

import argparse
import logging
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .auth import derive_key
from .bootstrap import build
from .config import Settings
from .http import MAX_BODY_BYTES, App, Request, Response
from .service import PickupService
from .storage import LocalStorage, is_valid_key

log = logging.getLogger("eloop.devserver")


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], bytes | None]:
    message = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body
    )
    fields: dict[str, str] = {}
    file_bytes: bytes | None = None
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if part.get_filename() is not None:
            file_bytes = part.get_payload(decode=True)
        elif isinstance(name, str):
            fields[name] = str(part.get_content())
    return fields, file_bytes


def make_handler(app: App, service: PickupService, storage: LocalStorage, max_upload: int):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _read(self, limit: int) -> bytes | None:
            length = int(self.headers.get("content-length") or 0)
            if length > limit:
                return None
            return self.rfile.read(length) if length else b""

        def _send(self, response: Response) -> None:
            payload = response.to_apigw()
            body = payload["body"].encode()
            self.send_response(payload["statusCode"])
            for key, value in payload["headers"].items():
                self.send_header(key, value)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status: int, code: str, message: str) -> None:
            self._send(Response(status, {"error": {"code": code, "message": message}}))

        def _dispatch(self) -> None:
            path = self.path.split("?", 1)[0]
            if self.command == "POST" and path == "/local-uploads":
                self._local_upload()
                return
            body = self._read(MAX_BODY_BYTES)
            if body is None:
                self._error(413, "PAYLOAD_TOO_LARGE", "Request body is too large")
                return
            request = Request(
                method=self.command,
                path=path,
                headers={k.lower(): v for k, v in self.headers.items()},
                body=body,
            )
            self._send(app.handle(request))

        def _local_upload(self) -> None:
            body = self._read(max_upload + 4096)
            if body is None:
                self._error(413, "PAYLOAD_TOO_LARGE", "Image is too large")
                return
            fields, data = parse_multipart(self.headers.get("content-type", ""), body)
            key = fields.get("key", "")
            if not data or not is_valid_key(key) or len(data) > max_upload:
                self._error(400, "INVALID_UPLOAD", "Invalid upload")
                return
            storage.save(key, data)
            self.send_response(204)
            self.send_header("content-length", "0")
            self.end_headers()

        do_GET = do_POST = do_PUT = do_DELETE = _dispatch  # noqa: N815

        def log_message(self, fmt: str, *args: object) -> None:
            log.info("%s %s", self.command, self.path)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    settings = Settings.from_env()
    if settings.mode != "local":
        raise SystemExit("devserver only runs with ELOOP_MODE=local")
    app, service = build(settings)
    storage = service.storage
    assert isinstance(storage, LocalStorage)

    print(f"\nE-Loop API on http://{args.host}:{args.port}  (local mode, data in {settings.local_data_dir}/)")
    print("\nCollector sign-in keys for this dev secret:")
    for collector_id in service.collector_ids():
        print(f"  {collector_id:<16} {derive_key(settings.collector_secret, collector_id)}")
    print()

    handler = make_handler(app, service, storage, settings.max_upload_bytes)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
