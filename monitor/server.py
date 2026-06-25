"""
monitor/server.py — web dashboard for Telegram AutoRPG.
Proxies API requests to the bot and queries Docker socket for container status.
"""
import asyncio
import json
import logging
import os
import socket
import time
from aiohttp import web, ClientSession, ClientConnectorError

API_URL = os.getenv("API_URL", "http://localhost:8081")
COMPOSE_PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "tg_autorpg")
DOCKER_SOCK = "/var/run/docker.sock"
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("monitor")


async def _fetch_json(url):
    last_exc = None
    for attempt in range(1, 4):
        try:
            async with ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    body = await resp.json(content_type=None)
                    return resp.status, body
        except (ClientConnectorError, OSError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if attempt < 3:
                await asyncio.sleep(0.5 * attempt)
    return 502, {"error": f"Upstream unavailable: {last_exc}"}


async def proxy_stats(request):
    status, data = await _fetch_json(f"{API_URL}/api/stats")
    return web.json_response(data, status=status)


async def proxy_players(request):
    search = request.query.get("search", "")
    url = f"{API_URL}/api/players"
    if search:
        url += f"?search={search}"
    status, data = await _fetch_json(url)
    return web.json_response(data, status=status)


async def proxy_player_detail(request):
    uid = request.match_info.get("uid")
    status, data = await _fetch_json(f"{API_URL}/api/players/{uid}")
    if status == 404:
        return web.json_response({"error": "Player not found"}, status=404)
    return web.json_response(data, status=status)


def _http_get_unix(request_bytes: bytes) -> dict:
    """Send raw HTTP request over Unix socket, return parsed JSON body.

    Handles Content-Length, Transfer-Encoding: chunked, and close-delimited
    (no length header, body ends at EOF) responses.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    sock.connect(DOCKER_SOCK)
    try:
        sock.sendall(request_bytes)

        buf = bytearray()
        header_end = -1
        length = None
        chunked = False

        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            buf.extend(chunk)

            if header_end == -1 and b"\r\n\r\n" in buf:
                header_end = buf.index(b"\r\n\r\n") + 4
                header_block = buf[:header_end].decode("utf-8", errors="replace")
                headers_lower = header_block.lower()

                if "content-length:" in headers_lower:
                    for line in header_block.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            length = int(line.split(":", 1)[1].strip())
                            break
                elif "transfer-encoding: chunked" in headers_lower:
                    chunked = True

            if header_end == -1:
                continue

            body = buf[header_end:]

            if length is not None:
                if len(body) >= length:
                    body = bytes(body[:length])
                    return json.loads(body.decode("utf-8", errors="replace"))
            elif chunked:
                decoded = bytearray()
                pos = 0
                complete = True
                while pos < len(body):
                    crlf = body.find(b"\r\n", pos)
                    if crlf == -1:
                        complete = False
                        break
                    size_str = body[pos:crlf].decode("ascii", errors="replace").strip()
                    try:
                        size = int(size_str, 16)
                    except ValueError:
                        complete = False
                        break
                    if size == 0:
                        return json.loads(bytes(decoded).decode("utf-8", errors="replace"))
                    chunk_end = crlf + 2 + size + 2
                    if len(body) < chunk_end:
                        complete = False
                        break
                    decoded.extend(body[crlf + 2:crlf + 2 + size])
                    pos = chunk_end
                if complete:
                    return json.loads(bytes(decoded).decode("utf-8", errors="replace"))
            else:
                if not chunk:
                    return json.loads(body.decode("utf-8", errors="replace"))

        if header_end == -1:
            return json.loads(buf.decode("utf-8", errors="replace") or "null")
        return json.loads(buf[header_end:].decode("utf-8", errors="replace") or "null")
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _query_docker_containers():
    """Query Docker Engine API via Unix socket. Returns list of compose project containers."""
    if not os.path.exists(DOCKER_SOCK):
        return [{"error": "docker socket missing"}]

    try:
        list_req = (
            b"GET /containers/json?all=1 HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        containers_raw = _http_get_unix(list_req)
    except Exception as e:
        return [{"error": f"docker query failed: {e}"}]

    if not isinstance(containers_raw, list):
        return [{"error": f"unexpected payload type: {type(containers_raw).__name__}"}]

    now_ts = int(time.time())
    out = []
    for c in containers_raw:
        labels = c.get("Labels") or {}
        project = labels.get("com.docker.compose.project", "")
        if project != COMPOSE_PROJECT:
            continue

        name = (c.get("Names") or ["?"])[0].lstrip("/")
        state = c.get("State", "unknown")
        status = c.get("Status", "")
        created = c.get("Created", 0)
        image = c.get("Image", "")

        health_status = None
        try:
            cid = c.get("Id", "")
            if cid:
                inspect_req = (
                    f"GET /containers/{cid}/json HTTP/1.1\r\n"
                    f"Host: localhost\r\nConnection: close\r\n\r\n"
                ).encode("utf-8")
                insp = _http_get_unix(inspect_req)
                health = (insp.get("State") or {}).get("Health") or {}
                health_status = health.get("Status")
        except Exception:
            pass

        uptime_seconds = max(0, now_ts - int(created)) if created else 0

        out.append({
            "name": name,
            "service": labels.get("com.docker.compose.service", ""),
            "image": image,
            "state": state,
            "status": status,
            "health": health_status,
            "uptime_seconds": uptime_seconds,
        })

    out.sort(key=lambda x: x.get("service") or x.get("name", ""))
    return out


async def handle_status(request):
    """Composite status: bot (from upstream) + containers (from Docker socket)."""
    bot_status, bot_data = await _fetch_json(f"{API_URL}/api/bot")
    if bot_status != 200:
        bot_data = {"status": "unreachable", "alive": False, "db_connected": False}

    containers = await asyncio.get_event_loop().run_in_executor(
        None, _query_docker_containers
    )

    return web.json_response({
        "bot": bot_data,
        "containers": containers,
    })


async def handle_api_root(request):
    return web.json_response({
        "endpoints": {
            "/api/stats": "Global statistics",
            "/api/status": "Bot + container status",
            "/api/players": "Player list (?search=name)",
            "/api/players/{uid}": "Player detail",
        }
    })


def main():
    app = web.Application()
    app.router.add_get("/api", handle_api_root)
    app.router.add_get("/api/stats", proxy_stats)
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/players", proxy_players)
    app.router.add_get("/api/players/{uid}", proxy_player_detail)
    app.router.add_static("/", path="./static", show_index=True)

    port = int(os.getenv("PORT", "8082"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    import aiohttp
    main()
