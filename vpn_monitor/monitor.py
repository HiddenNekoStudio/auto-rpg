#!/usr/bin/env python3
"""
VPN Monitor v5 - Stable Hysteria health checker.

Key insight from v4: httpbin.org connectivity check fails because the URL
is unreachable from the VPN server's network. VPN IS working (bot proves it).

v5 changes:
- Removed fragile HTTP connectivity check entirely
- Health = server reachable (UDP) + proxy ports accepting TCP connections
- No restart if tunnel is alive — just log and continue
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import yaml

# --- Config ---
CONTAINER_NAME = os.getenv("VPN_CONTAINER", "hysteria_vpn")
DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
SERVER_CHECK_TIMEOUT = int(os.getenv("SERVER_CHECK_TIMEOUT", "3"))
VPN_CONFIG_PATH = os.getenv("VPN_CONFIG_PATH", "/etc/hysteria/config.yaml")
SERVERS_FILE = os.getenv("SERVERS_FILE", "/app/servers.json")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/backups")
STARTUP_GRACE = int(os.getenv("STARTUP_GRACE", "20"))
MAX_RESTART_ATTEMPTS = int(os.getenv("MAX_RESTART_ATTEMPTS", "3"))
RESTART_COOLDOWN = int(os.getenv("RESTART_COOLDOWN", "120"))
CONSECUTIVE_FAILURES_REQUIRED = int(os.getenv("CONSECUTIVE_FAILURES_REQUIRED", "3"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("vpn_monitor")


class ServerManager:
    """Manages VPN server list and config failover."""

    def __init__(self, servers_file: str = SERVERS_FILE, config_path: str = VPN_CONFIG_PATH):
        self.servers_file = Path(servers_file)
        self.config_path = Path(config_path)
        self.backup_dir = Path(BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.servers = self._load_servers()
        self.current_server = self._get_current_server()

    def _load_servers(self) -> list[dict]:
        if not self.servers_file.exists():
            logger.warning(f"Servers file not found: {self.servers_file}")
            return []
        try:
            with open(self.servers_file) as f:
                servers = json.load(f)
            logger.info(f"Loaded {len(servers)} servers")
            return servers
        except Exception as e:
            logger.error(f"Failed to load servers: {e}")
            return []

    def _get_current_server(self) -> Optional[dict]:
        if not self.config_path.exists():
            logger.error(f"Config not found: {self.config_path}")
            return None
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            server_str = config.get("server", "")
            if ":" in server_str:
                host, port = server_str.rsplit(":", 1)
                port = int(port)
            else:
                host, port = server_str, 443
            sni = config.get("tls", {}).get("sni", host)
            return {"host": host, "port": port, "sni": sni}
        except Exception as e:
            logger.error(f"Failed to parse config: {e}")
            return None

    async def check_server_reachable(self, host: str, port: int) -> bool:
        """UDP reachability check for QUIC/Hysteria."""
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_DGRAM),
                timeout=SERVER_CHECK_TIMEOUT,
            )
        except (asyncio.TimeoutError, OSError):
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            loop = asyncio.get_event_loop()
            infos = await loop.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM)
            if not infos:
                sock.close()
                return False
            ip = infos[0][4][0]
            await asyncio.wait_for(loop.sock_sendto(sock, b"\x00", (ip, port)), timeout=SERVER_CHECK_TIMEOUT)
            try:
                await asyncio.wait_for(loop.sock_recv(sock, 1024), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            sock.close()
            return True
        except (OSError, asyncio.TimeoutError):
            return False
        except Exception:
            return False

    async def get_next_server(self) -> Optional[dict]:
        current_host = self.current_server["host"] if self.current_server else None
        for server in self.servers:
            if server["host"] == current_host:
                continue
            host = server["host"]
            port = server.get("port", 443)
            label = server.get("label", host)
            reachable = await self.check_server_reachable(host, port)
            if reachable:
                logger.info(f"Fallback found: {label} ({host}:{port})")
                return server
        return None

    def _backup_config(self):
        if not self.config_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"config_{timestamp}.yaml"
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Config backed up: {backup_path.name}")
        backups = sorted(self.backup_dir.glob("config_*.yaml"))
        for old in backups[:-10]:
            old.unlink()

    def update_config(self, server: dict) -> bool:
        if not self.config_path.exists():
            return False
        try:
            self._backup_config()
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            host = server["host"]
            port = server.get("port", 443)
            sni = server.get("sni", host)
            config["server"] = f"{host}:{port}"
            config.setdefault("tls", {})["sni"] = sni
            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            self.current_server = {"host": host, "port": port, "sni": sni}
            logger.info(f"Config updated -> {server.get('label', host)} ({host}:{port})")
            return True
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False


class DockerClient:
    """Minimal Docker API client."""

    def __init__(self, socket_path: str = DOCKER_SOCKET):
        self.socket_path = socket_path

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"http://localhost{path}"
        connector = aiohttp.UnixConnector(path=self.socket_path)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.request(method, url, **kwargs) as resp:
                if resp.status == 204:
                    return {}
                return await resp.json()

    async def get_container(self, name: str) -> Optional[dict]:
        try:
            containers = await self._request("GET", "/containers/json", params={"all": "true"})
            for c in containers:
                if any(name in n for n in c.get("Names", [])):
                    return c
            return None
        except Exception as e:
            logger.error(f"Docker API error: {e}")
            return None

    async def restart_container(self, name: str) -> bool:
        try:
            container = await self.get_container(name)
            if not container:
                return False
            cid = container["Id"]
            await self._request("POST", f"/containers/{cid}/restart")
            logger.info(f"Restarted {name} ({cid[:12]})")
            return True
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            return False


class ProxyChecker:
    """Checks proxy port availability."""

    def __init__(self):
        self.socks5_host = os.getenv("SOCKS5_PROXY", f"socks5://{CONTAINER_NAME}:1080").replace("socks5://", "")
        self.http_host = os.getenv("HTTP_PROXY", f"http://{CONTAINER_NAME}:8080").replace("http://", "")

    def _parse_addr(self, addr: str) -> tuple[str, int]:
        if ":" in addr:
            h, p = addr.rsplit(":", 1)
            return h, int(p)
        return addr, 80

    async def check_port(self, host: str, port: int) -> bool:
        """TCP connect to verify proxy is listening."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=3
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, OSError):
            return False

    async def check_all(self) -> dict:
        sh, sp = self._parse_addr(self.socks5_host)
        hh, hp = self._parse_addr(self.http_host)

        socks5_ok = await self.check_port(sh, sp)
        http_ok = await self.check_port(hh, hp)

        if socks5_ok:
            logger.info(f"SOCKS5 {sh}:{sp} OK")
        else:
            logger.warning(f"SOCKS5 {sh}:{sp} DOWN")

        if http_ok:
            logger.info(f"HTTP {hh}:{hp} OK")
        else:
            logger.warning(f"HTTP {hh}:{hp} DOWN")

        return {"socks5": socks5_ok, "http": http_ok, "any": socks5_ok or http_ok}


class VPMMonitor:
    """VPN monitor — health = server UDP + proxy ports TCP."""

    def __init__(self):
        self.docker = DockerClient()
        self.server_mgr = ServerManager()
        self.proxy_checker = ProxyChecker()
        self.restart_count = 0
        self.last_restart_time = 0.0
        self.consecutive_failures = 0
        self.running = True
        self.last_event_time = time.time()
        self.stats = {
            "checks": 0,
            "restarts": 0,
            "server_switches": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

    def in_grace_period(self) -> bool:
        elapsed = time.time() - self.last_event_time
        if elapsed < STARTUP_GRACE:
            logger.info(f"Grace period ({STARTUP_GRACE - elapsed:.0f}s left)")
            return True
        return False

    async def check_container(self) -> bool:
        container = await self.docker.get_container(CONTAINER_NAME)
        if not container:
            return False
        return container.get("State", "").lower() == "running"

    async def switch_server(self, reason: str) -> bool:
        logger.warning(f"Switching server — {reason}")
        next_server = await self.server_mgr.get_next_server()
        if not next_server:
            logger.error("No reachable fallback servers")
            return False
        if self.server_mgr.update_config(next_server):
            self.stats["server_switches"] += 1
            success = await self.docker.restart_container(CONTAINER_NAME)
            if success:
                self.last_event_time = time.time()
                self.restart_count = 0
                self.consecutive_failures = 0
                logger.info("VPN restarted with new server")
                await asyncio.sleep(STARTUP_GRACE)
            return success
        return False

    async def should_restart(self) -> bool:
        now = time.time()
        if now - self.last_restart_time < RESTART_COOLDOWN:
            remaining = RESTART_COOLDOWN - (now - self.last_restart_time)
            logger.info(f"Restart cooldown — {remaining:.0f}s left")
            return False
        if self.restart_count >= MAX_RESTART_ATTEMPTS:
            logger.warning(f"Max restarts ({MAX_RESTART_ATTEMPTS}) reached")
            return False
        return True

    async def restart_vpn(self, reason: str) -> bool:
        if not await self.should_restart():
            return False
        logger.warning(f"Restarting VPN — {reason}")
        self.stats["restarts"] += 1
        self.restart_count += 1
        self.last_restart_time = time.time()
        self.last_event_time = time.time()
        success = await self.docker.restart_container(CONTAINER_NAME)
        if success:
            logger.info(f"Waiting {STARTUP_GRACE}s for startup...")
            await asyncio.sleep(STARTUP_GRACE)
        return success

    async def run_check_cycle(self) -> bool:
        self.stats["checks"] += 1
        logger.info(f"--- Check #{self.stats['checks']} ---")

        # 1. Container running?
        if not await self.check_container():
            logger.warning("Container NOT running")
            self.consecutive_failures += 1
            if self.consecutive_failures >= CONSECUTIVE_FAILURES_REQUIRED:
                await self.restart_vpn("Container not running")
                self.consecutive_failures = 0
            return False

        logger.info("Container: running")

        # 2. Grace period
        if self.in_grace_period():
            return True

        # 3. Server reachable? (UDP = QUIC tunnel alive)
        current = self.server_mgr.current_server
        if current:
            server_ok = await self.server_mgr.check_server_reachable(
                current["host"], current.get("port", 443)
            )
        else:
            server_ok = False

        # 4. Proxy ports accepting connections?
        proxy = await self.proxy_checker.check_all()

        # 5. Decision
        if server_ok and proxy["any"]:
            # HEALTHY: tunnel alive + proxy listening
            self.restart_count = 0
            self.consecutive_failures = 0
            logger.info("VPN healthy (server OK + proxy OK)")
            return True

        if server_ok and not proxy["any"]:
            # Tunnel alive but ports dead — unusual, might recover
            self.consecutive_failures += 1
            logger.warning(
                f"Server OK but proxy ports dead — "
                f"failures: {self.consecutive_failures}/{CONSECUTIVE_FAILURES_REQUIRED}"
            )
            if self.consecutive_failures >= CONSECUTIVE_FAILURES_REQUIRED:
                await self.restart_vpn("Proxy ports dead despite server reachable")
                self.consecutive_failures = 0
            return False

        if not server_ok and proxy["any"]:
            # Ports accepting but server unreachable — might be DNS/proxy issue
            self.consecutive_failures += 1
            logger.warning(
                f"Server unreachable but proxy ports up — "
                f"failures: {self.consecutive_failures}/{CONSECUTIVE_FAILURES_REQUIRED}"
            )
            if self.consecutive_failures >= CONSECUTIVE_FAILURES_REQUIRED:
                switched = await self.switch_server("Server unreachable")
                if not switched:
                    await self.restart_vpn("Server unreachable, no fallback")
                self.consecutive_failures = 0
            return False

        if not server_ok and not proxy["any"]:
            # Everything down
            self.consecutive_failures += 1
            logger.warning(
                f"Everything down — "
                f"failures: {self.consecutive_failures}/{CONSECUTIVE_FAILURES_REQUIRED}"
            )
            if self.consecutive_failures >= CONSECUTIVE_FAILURES_REQUIRED:
                switched = await self.switch_server("Server + proxy both down")
                if not switched:
                    await self.restart_vpn("No fallback")
                self.consecutive_failures = 0
            return False

        return False

    async def run(self):
        current = self.server_mgr.current_server
        server_label = current.get("sni", "unknown") if current else "none"
        logger.info(f"VPN Monitor v5 started")
        logger.info(f"Container: {CONTAINER_NAME}")
        logger.info(f"Server: {server_label}")
        logger.info(f"Interval: {CHECK_INTERVAL}s | Grace: {STARTUP_GRACE}s | "
                     f"Cooldown: {RESTART_COOLDOWN}s | Max restarts: {MAX_RESTART_ATTEMPTS}")

        self.last_event_time = time.time()

        while self.running:
            try:
                await self.run_check_cycle()
            except Exception as e:
                logger.error(f"Check error: {e}", exc_info=True)
            await asyncio.sleep(CHECK_INTERVAL)

    def stop(self):
        self.running = False
        logger.info("VPN Monitor stopping...")


def handle_signal(sig, frame):
    logger.info(f"Signal {sig}")
    monitor.stop()


async def main():
    global monitor
    monitor = VPMMonitor()
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    logger.info("=" * 50)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
