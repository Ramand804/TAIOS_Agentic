import argparse
from core.orchestrator import Orchestrator
from core.experiment import DEFAULT_SIMULATION_START

def main():
    p = argparse.ArgumentParser(description="TAIOS deterministic scenario runner")
    p.add_argument("--scenario", default="S1", choices=[f"S{i}" for i in range(1,7)])
    p.add_argument("--events", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--log-dir", default="logs")
    p.add_argument("--simulation-start-time", default=DEFAULT_SIMULATION_START)
    p.add_argument("--event-interval-seconds", type=float, default=1.0)
    args = p.parse_args()

    runner = Orchestrator(seed=args.seed, log_dir=args.log_dir,
                          simulation_start_time=args.simulation_start_time,
                          event_interval_seconds=args.event_interval_seconds)
    events = runner.run_scenario(args.scenario, args.events)
    print(f"TAIOS generated {len(events)} events for {args.scenario}")
    print(f"Experiment: {runner.experiment.experiment_id}")
    print(f"Fingerprint: {runner.fingerprint}")
    for e in events[:3]:
        print(e.to_dict())

if __name__ == "__main__":
    main()
