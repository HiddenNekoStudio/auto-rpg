#!/usr/bin/env python3
import asyncio
import aiohttp


async def main():
    async with aiohttp.ClientSession() as s:
        r = await s.get("http://localhost:8081/health")
        exit(0 if r.status < 500 else 1)


asyncio.run(main())
