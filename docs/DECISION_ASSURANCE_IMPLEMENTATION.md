# Milestone 8B: Decision-Causal Assurance Gate

The assurance gate is stateless and sits after frozen autonomous-authority assessment and before final decision context, planning, decision, governance, and execution. It receives bound assessment artifacts and can only remove ALLOW or MONITOR authority, adding REQUEST_APPROVAL solely as a deferral path. It cannot create autonomous authority, change authorization, change semantic validity, or modify governance.

Direct threat evidence, direct correlation evidence, and persistent unexplained drift can require review. Risk is recorded with coverage and never thresholds a decision. Trust degradation is recorded only alongside independent adverse evidence. A valid known regime change is explicitly exempt from drift-only restriction. Correlation uncertainty is not adverse confirmation.

ASSURANCE_OFF preserves existing authority. ASSURANCE_ON uses the same deterministic policy for STATIC, ADAPTIVE, and NoTrust pipelines. RULE_BASED remains assurance-disabled from the 8A comparison.

In current scenarios, S2 events 6–10 already lack permissive authority due operational invalidity, so adverse evidence is reported as `ALREADY_RESTRICTED_UPSTREAM`; assurance does not claim credit for their review actions. S5 HIGH_OUTPUT remains autonomous because it is a valid known regime change. No future discriminating scenarios were introduced. The gate uses no evaluator labels, learned models, LLMs, or policy tuning.
