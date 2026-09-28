# Ablation and publication experiment

Experiment `milestone8d-publication-ablation-v1` uses 20 fixed seeds, seven valid configurations, nine frozen scenarios, and 1,260 episodes. Each scenario/seed stream is generated once and reused across configurations; seeds are replication units and events are not independent replicates. S1--S6 use 10 events and S7--S9 use 50, giving 4,200 unique scenario/seed events.

Both event-weighted and scenario-balanced views are retained in the derived table data. Primary paired comparisons use seed-level unsafe rates; constant differences have no effect size or test statistic. `NO_GOVERNANCE` is excluded because governance creates the authorization artifact required by execution integrity.

S7 action changes are caused by persistent unexplained drift through assurance, not by direct threat evidence or dynamic trust. S8 is an explained regime change; S9 returns autonomy but does not demonstrate trust recovery. The frozen publication SHA is `92c0f6486045e9639cd3c873c1b8853c0024ffbd3f9201e5a76ddb85a8d1dc84`; deterministic validation SHA is `ce22ff17871784f2867a2ac25c7b08dfe11d06fbe7a9cb6f1dd192b5aba4b3f9`.

The stale validation artifact incident contained wall-clock timing. It was non-semantic; scientific records matched the publication five-seed subset. Timing remains excluded from deterministic semantic artifacts. Limitations include synthetic scenarios, uncalibrated security signals, no direct S7 threat evidence, no ML/LLM/LangGraph, and no real-world or hard-real-time validation.
