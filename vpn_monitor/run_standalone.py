#!/usr/bin/env python3
"""
VPN Monitor — standalone runner (no Docker required).

Usage:
    python3 run_standalone.py              # Run with defaults
    python3 run_standalone.py --once       # Single check then exit
    python3 run_standalone.py --status     # Show container + server status
    python3 run_standalone.py --servers    # List all servers and reachability
    python3 run_standalone.py --switch     # Force switch to next server

Requires: Docker socket accessible at /var/run/docker.sock
"""

import argparse
import asyncio
import json
import sys

from monitor import CONTAINER_NAME, DockerClient, ServerManager, VPMMonitor, logger


async def show_status():
    """Print current VPN status."""
    docker = DockerClient()
    container = await docker.get_container(CONTAINER_NAME)
    server_mgr = ServerManager()

    if not container:
        print(f"Container '{CONTAINER_NAME}' not found")
        return False

    state = container.get("State", "unknown")
    container_id = container.get("Id", "")[:12]
    image = container.get("Image", "")

    print(f"Container: {CONTAINER_NAME}")
    print(f"ID:        {container_id}")
    print(f"Image:     {image}")
    print(f"State:     {state}")

    # Server info
    current = server_mgr.current_server
    if current:
        print(f"\nCurrent server: {current.get('sni', current['host'])} ({current['host']}:{current.get('port', 443)})")
        reachable = await server_mgr.check_server_reachable(current["host"], current.get("port", 443))
        print(f"Server reachable: {'YES' if reachable else 'NO'}")

    # Show recent logs
    logs = await docker.get_container_logs(CONTAINER_NAME, tail=10)
    if logs:
        print(f"\nRecent logs:\n{logs}")

    return state.lower() == "running"


async def list_servers():
    """List all servers with reachability status."""
    server_mgr = ServerManager()
    current = server_mgr.current_server

    print("VPN Servers:")
    print("-" * 60)
    for server in server_mgr.servers:
        host = server["host"]
        port = server.get("port", 443)
        label = server.get("label", host)
        is_current = current and host == current["host"]
        reachable = await server_mgr.check_server_reachable(host, port)

        marker = " *" if is_current else "  "
        status = "OK" if reachable else "DOWN"
        print(f"{marker} {label:8} {host}:{port} [{status}]")

    print("-" * 60)
    print("(* = current server)")


async def force_switch():
    """Force switch to next server."""
    server_mgr = ServerManager()
    current = server_mgr.current_server

    if current:
        print(f"Current: {current.get('sni', current['host'])}")

    next_server = await server_mgr.get_next_server()
    if not next_server:
        print("No reachable servers available")
        return False

    label = next_server.get("label", next_server["host"])
    print(f"Switching to: {label} ({next_server['host']}:{next_server.get('port', 443)})")

    if server_mgr.update_config(next_server):
        print("Config updated successfully")

        docker = DockerClient()
        if await docker.restart_container(CONTAINER_NAME):
            print("VPN container restarted")
            return True
        else:
            print("Failed to restart VPN container")
            return False
    else:
        print("Failed to update config")
        return False


async def single_check():
    """Run a single health check."""
    monitor = VPMMonitor()
    healthy = await monitor.run_check_cycle()
    return healthy


async def run_forever():
    """Run continuous monitoring."""
    monitor = VPMMonitor()
    await monitor.run()


def main():
    parser = argparse.ArgumentParser(description="VPN Monitor")
    parser.add_argument("--once", action="store_true", help="Single check then exit")
    parser.add_argument("--status", action="store_true", help="Show container + server status")
    parser.add_argument("--servers", action="store_true", help="List all servers with reachability")
    parser.add_argument("--switch", action="store_true", help="Force switch to next server")
    args = parser.parse_args()

    if args.status:
        ok = asyncio.run(show_status())
        sys.exit(0 if ok else 1)
    elif args.servers:
        asyncio.run(list_servers())
    elif args.switch:
        ok = asyncio.run(force_switch())
        sys.exit(0 if ok else 1)
    elif args.once:
        ok = asyncio.run(single_check())
        sys.exit(0 if ok else 1)
    else:
        asyncio.run(run_forever())


if __name__ == "__main__":
    main()
