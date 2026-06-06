import socket
import ssl
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from app.config import ENV_PATH, get_settings


def main() -> int:
    load_dotenv(ENV_PATH)
    settings = get_settings()
    ok = True

    supabase_ok, supabase_detail = check_supabase_tables(settings)
    print(f"supabase: {'OK' if supabase_ok else 'FAIL'} - {supabase_detail}")
    ok = ok and supabase_ok

    redis_ok, redis_detail = check_redis(settings.devlens_redis_url or settings.redis_url)
    print(f"redis: {'OK' if redis_ok else 'FAIL'} - {redis_detail}")
    ok = ok and redis_ok

    return 0 if ok else 1


def check_supabase_tables(settings) -> tuple[bool, str]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return False, "missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
    tables = ["jobs", "users", "cv_scores"]
    statuses = []
    try:
        for table in tables:
            response = httpx.get(
                f"{settings.supabase_url}/rest/v1/{table}",
                params={"select": "id", "limit": "1"},
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
                timeout=10,
            )
            if response.status_code not in {200, 206}:
                return False, f"HTTP {response.status_code}; public.{table} read probe failed"
            statuses.append(f"public.{table}")
        return True, f"{', '.join(statuses)} reachable"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def check_redis(redis_url: str | None) -> tuple[bool, str]:
    if not redis_url:
        return False, "missing DEVLENS_REDIS_URL or REDIS_URL"
    parsed = urlparse(redis_url)
    try:
        host = parsed.hostname
        port = parsed.port or (6380 if parsed.scheme == "rediss" else 6379)
        if not host:
            return False, "missing Redis host"
        raw_sock = socket.create_connection((host, port), timeout=10)
        use_tls = parsed.scheme == "rediss" or port == 6380
        sock = ssl.create_default_context().wrap_socket(raw_sock, server_hostname=host) if use_tls else raw_sock
        with sock:
            sock.settimeout(10)
            _redis_auth(sock, parsed.username, parsed.password)
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            pong = sock.recv(4096)
            if pong.startswith(b"+PONG"):
                return True, "PING returned PONG"
            return False, "PING returned an unexpected response"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _redis_auth(sock, username: str | None, password: str | None) -> None:
    if not password:
        return
    if username:
        command = f"*3\r\n$4\r\nAUTH\r\n${len(username)}\r\n{username}\r\n${len(password)}\r\n{password}\r\n"
    else:
        command = f"*2\r\n$4\r\nAUTH\r\n${len(password)}\r\n{password}\r\n"
    sock.sendall(command.encode("utf-8"))
    response = sock.recv(4096)
    if not response.startswith(b"+OK"):
        raise RuntimeError("Redis AUTH failed")


if __name__ == "__main__":
    raise SystemExit(main())
