"""Measure deterministic in-memory lifecycle latency; does not execute a process command."""
import statistics
import time
from datetime import datetime, timezone
from industrial.gateway.types import IndustrialRuntimeEvent, SynchronizedIndustrialState
from industrial.runtime.governance import IndustrialGovernance, OperatingMode
from industrial.trusted_runtime import build_trusted_runtime

N = datetime(2026, 1, 1, tzinfo=timezone.utc)

def event(index):
    return IndustrialRuntimeEvent(f"measurement-{index}", N, "PRODUCTION_CONTROLLER", "controller", "MIXER", "mixer", "engineering-01", "control_command", "START_ASSET", None, "testbed", "OPC_UA", True, .85, {"state_version": 0})

def main():
    samples=[]
    for index in range(100):
        runtime=build_trusted_runtime(IndustrialGovernance(OperatingMode.SIMULATION, lambda:N), lambda:N)
        start=time.perf_counter_ns()
        runtime.lifecycle.assess(event(index), SynchronizedIndustrialState({},0))
        samples.append((time.perf_counter_ns()-start)/1_000_000)
    print({"samples":len(samples), "median_ms":round(statistics.median(samples),4), "p95_ms":round(sorted(samples)[94],4), "mode":"SIMULATION", "process_mutations":0})
if __name__ == '__main__': main()
