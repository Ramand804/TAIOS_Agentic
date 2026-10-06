# Semantic and policy coupling analysis

| File | Class/function | Dependency | Classification | Safe parameterization | V1 risk |
|---|---|---|---|---|---|
| `environment/assets.py` | `ASSET_REGISTRY`, `get_asset` | V1 scenario assets | policy data | No caller-local provider seam | high |
| `environment/identities.py` | `DEFAULT_IDENTITIES` | V1 identities | policy data | No provider seam | high |
| `environment/operational_limits.py` | `OperationalLimits` | V1 asset/operation/mode limits | policy data plus check API | Direct construction downstream | high |
| `intelligence/operational_semantic_model.py` | `OperationalSemanticModel` | `OperationalSemanticRegistry`, `OperationalLimits` | mechanism fused with V1 policy | Constructor requires exact concrete V1 types; rule and limit behavior is embedded in `assess` | high |
| `intelligence/authorization_engine.py` | `AuthorizationEngine` | V1 assets, identities, `PermissionPolicy` | mechanism fused with V1 policy | Constructor snapshots V1 globals and evaluates V1 role/asset rules directly | high |
| `intelligence/decision_context_builder.py` | `build_decision_context` | direct `OperationalLimits()` construction | capability mechanism fused with V1 limits | Requires an explicit limit provider and capability representation change | high |
| `core/runtime_inputs.py` | `runtime_observation` | frozen `IndustrialEvent` projection | adapter boundary | Cannot accept `IndustrialRuntimeEvent` directly | medium |
| `core/taios_pipeline.py` | `_event_observation`, `process_event` | `EventManager`, experimental event | transaction mechanism coupled to experiment contract | Separate runtime transaction core required | high |

## Finding

The V1 semantic and authorization mechanisms are not currently policy-provider consumers. Their policy data, concrete types, and decision semantics are coupled in the same APIs. A testbed profile cannot be introduced merely by supplying registry data: it would require changing core constructors, validation types, capability building, and the pipeline transaction boundary.

That refactor would create a new runtime semantic/authorization core whose equivalence to V1 is not locally demonstrable without a full architectural extraction. It is outside the safe structural parameterization permitted for this intermediate milestone.
