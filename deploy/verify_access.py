"""Check the public endpoint without using or printing administrator credentials."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ORIGIN = "https://chat.tampak.my.id"


def check(path: str, expected: int, *, method: str = "GET") -> bytes:
    request = Request(ORIGIN + path, method=method, headers={"Origin": ORIGIN})
    try:
        with urlopen(request, timeout=20) as response:
            status, body = response.status, response.read()
    except HTTPError as error:
        status, body = error.code, error.read()
    if status != expected:
        raise AssertionError(f"{method} {path}: expected HTTP {expected}, got {status}")
    return body


def main() -> None:
    check("/", 200)
    assert json.loads(check("/api/v1/health", 200))["status"] == "ok"
    check("/api/v1/bots", 401)
    error = json.loads(check("/api/v1/session/guest", 401, method="POST"))
    assert error["error"]["code"] == "AUTH_REQUIRED"
    check("/.env", 404)
    print("Verified HTTPS, healthy API, required login, disabled guest sessions and private configuration.")


if __name__ == "__main__":
    main()
