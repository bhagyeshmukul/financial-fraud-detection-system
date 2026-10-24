"""
Send controlled HTTP traffic and measure completed requests, failures and latency. Optional
process-tree memory sampling observes the local API; it does not prove cloud capacity.
"""

import argparse
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
import httpx
import numpy as np
import psutil


async def run(args):
    """
    Run bounded asynchronous traffic, exclude warmup, and write measured latency/error/memory
    results.
    """
    if args.pid:
        psutil.Process(
            args.pid
        )  # Fail before issuing traffic if the supplied PID is stale.
    headers = (
        {"Authorization": f"Bearer {os.environ['API_ACCESS_TOKEN']}"}
        if os.getenv("API_ACCESS_TOKEN")
        else {}
    )
    async with httpx.AsyncClient(
        base_url=args.url,
        headers=headers,
        timeout=30,
        limits=httpx.Limits(max_connections=20),
    ) as client:
        samples = (
            (await client.get(f"/api/v1/profiles/{args.profile}/samples"))
            .raise_for_status()
            .json()["samples"]
        )
        session = (
            (
                await client.post(
                    "/api/v1/sessions",
                    json={"profile": args.profile, "seeded": args.profile == "banksim"},
                )
            )
            .raise_for_status()
            .json()["id"]
        )
        latencies, errors = [], []
        semaphore = asyncio.Semaphore(20)

        async def request(index, scheduled_at=None):
            """
            Send one scheduled HTTP request, record its completion or error, and release its
            concurrency slot.
            """
            arrival = time.perf_counter() if scheduled_at is None else scheduled_at
            async with semaphore:
                try:
                    response = await client.post(
                        f"/api/v1/profiles/{args.profile}/predictions",
                        json={
                            "session_id": session,
                            "request_id": str(uuid.uuid4()),
                            "transaction": samples[index % len(samples)]["payload"],
                        },
                    )
                    response.raise_for_status()
                    latencies.append((time.perf_counter() - arrival) * 1000)
                except Exception as error:
                    errors.append(f"{type(error).__name__}: {error}"[:200])

        await request(
            0
        )  # Warm the model; exclude this request from the timed measurement.
        if errors:
            raise RuntimeError(errors[0])
        latencies.clear()
        started = time.perf_counter()
        memory = []
        next_memory_sample = started
        tasks = []
        # Schedule requests at the requested arrival rate; queue delay remains part of measured latency.
        for index in range(round(args.rps * args.seconds)):
            delay = started + index / args.rps - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            tasks.append(
                asyncio.create_task(request(index, started + index / args.rps))
            )
            if args.pid and time.perf_counter() >= next_memory_sample:
                next_memory_sample = time.perf_counter() + 1
                process = psutil.Process(args.pid)
                memory.append(
                    sum(
                        p.memory_info().rss
                        for p in [process, *process.children(recursive=True)]
                        if p.is_running()
                    )
                )
        await asyncio.gather(*tasks)
        await asyncio.sleep(max(0, started + args.seconds - time.perf_counter()))
        elapsed = time.perf_counter() - started
        result = {
            "profile": args.profile,
            "target_rps": args.rps,
            "duration_requested_s": args.seconds,
            "duration_actual_s": elapsed,
            "successful_requests": len(latencies),
            "failures": len(errors),
            "throughput_rps": len(latencies) / elapsed,
            "latency_p50_ms": float(np.percentile(latencies, 50))
            if latencies
            else None,
            "latency_p95_ms": float(np.percentile(latencies, 95))
            if latencies
            else None,
            "latency_p99_ms": float(np.percentile(latencies, 99))
            if latencies
            else None,
            "peak_observed_rss_mb": max(memory) / 1024**2 if memory else None,
            "memory_scope": "supplied server PID and descendants"
            if args.pid
            else "not measured; supply --pid",
            "errors": errors[:5],
            "latency_scope": "scheduled arrival through response, including client concurrency queue",
            "memory_sampling_interval_s": 1,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        if errors:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--profile", choices=["credit_card", "banksim"], default="credit_card"
    )
    parser.add_argument("--rps", type=float, default=10)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=Path("artifacts/traffic.json"))
    arguments = parser.parse_args()
    if not (0 < arguments.rps <= 100 and 0 < arguments.seconds <= 3600):
        parser.error("Use 0 < rps <= 100 and 0 < seconds <= 3600.")
    asyncio.run(run(arguments))
