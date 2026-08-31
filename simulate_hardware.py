#!/usr/bin/env python3
"""Step 5 — mock field hardware.

Generates a synthetic Time-Domain EM (TDEM) decay, sprinkles in bad samples
(nulls, to be dropped by the Node.js sanitizer), and POSTs the batch to the
Fastify ingestion endpoint. This exercises the full pipeline:

    hardware -> Node.js (sanitize) -> WebSocket -> FastAPI -> agent -> sandbox -> result

The ingestion API is fire-and-forget: it returns a 202 with a jobId. The
converged inversion result is delivered asynchronously and shows up in the
Node.js and FastAPI logs. Run with --watch-note to print where to look.

Standard library only — no dependencies required to run the simulator.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

# A real empymod TDEM step-off transient over a 2-layer earth (air / 50 Ohm-m
# overburden to 40 m / 200 Ohm-m basement), generated once with
# empymod.dipole(..., signal=-1). This is the curve the Gemini agent inverts.
SIM_TIME = [
    1e-5, 1.333521e-5, 1.778279e-5, 2.371374e-5, 3.162278e-5, 4.216965e-5,
    5.623413e-5, 7.498942e-5, 1e-4, 1.333521e-4, 1.778279e-4, 2.371374e-4,
    3.162278e-4, 4.216965e-4, 5.623413e-4, 7.498942e-4, 1e-3, 1.333521e-3,
    1.778279e-3, 2.371374e-3, 3.162278e-3, 4.216965e-3, 5.623413e-3, 7.498942e-3, 1e-2,
]
SIM_AMP = [
    1.130264e-5, 1.094813e-5, 1.012592e-5, 8.77939e-6, 7.095997e-6, 5.392272e-6,
    3.911728e-6, 2.725708e-6, 1.848747e-6, 1.227547e-6, 8.021937e-7, 5.188348e-7,
    3.334073e-7, 2.132082e-7, 1.361586e-7, 8.662659e-8, 5.520318e-8, 3.545849e-8,
    2.250741e-8, 1.454127e-8, 9.26825e-9, 5.94527e-9, 3.825482e-9, 2.458338e-9, 1.581909e-9,
]


def build_payload(n_bad: int) -> dict:
    times = list(SIM_TIME)
    amplitudes = list(SIM_AMP)

    # Corrupt a few samples so the Node.js sanitizer has work to do. JSON has no
    # NaN, so bad samples are sent as null; the sanitizer drops those pairs.
    for k in range(n_bad):
        idx = (k * 6 + 3) % len(times)  # deterministic, spread out
        if k % 2 == 0:
            amplitudes[idx] = None
        else:
            times[idx] = None

    return {
        "sensorId": "sim-tdem-01",
        "dataType": "TDEM",
        "timeSteps": times,
        "amplitudes": amplitudes,
    }


def post(url: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock TDEM hardware -> Node ingestion")
    parser.add_argument("--url", default="http://localhost:3000/ingest/field-data")
    parser.add_argument("--bad", type=int, default=4)
    args = parser.parse_args()

    payload = build_payload(args.bad)
    print("Truth model: air / 50 Ohm-m to 40 m / 200 Ohm-m basement (empymod TDEM)")
    print(f"Posting {len(SIM_TIME)} samples ({args.bad} corrupted) to {args.url}")

    try:
        status, body = post(args.url, payload)
    except urllib.error.URLError as exc:
        print(f"ERROR: could not reach ingestion endpoint: {exc}")
        print("Is the Node.js server running on port 3000?")
        return 1

    print(f"HTTP {status}: {json.dumps(body, indent=2)}")
    print(
        "\nThe converged model is delivered asynchronously — watch the FastAPI "
        "and Node.js logs for the final inversion result for this jobId."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
