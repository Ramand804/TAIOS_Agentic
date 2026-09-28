"""Deterministic frozen-policy Milestone-8D ablation experiment runner."""
import argparse, json
from pathlib import Path
from time import perf_counter

from core.ablation_configuration import AblationConfiguration, SPECS, create_ablation_pipeline
from core.experiment import event_stream_fingerprint, fingerprint
from environment.event_generator import EventGenerator
from environment.scenarios import get_scenario_evaluation_metadata
from evaluation.formal_evaluator import TAIOSEvaluator
from evaluation.statistical_analysis import paired_difference, summary

SCENARIOS = tuple(f'S{i}' for i in range(1, 10))
VALIDATION_SEEDS = (42, 123, 456, 789, 2026)
PUBLICATION_SEEDS = VALIDATION_SEEDS + tuple(range(3001, 3016))
METRICS = ('exact_action_agreement','unsafe_action_rate','false_intervention_rate','proposal_review_burden','autonomous_execution_rate')

def event_count(s): return 50 if s in ('S7','S8','S9') else 10

def _metrics(episode, events):
    row = TAIOSEvaluator().evaluate_experiment(((episode, events),)).to_dict()['overall_results']
    return {k: row[k] for k in METRICS} | {'denominators': {
        'events': row['event_count'], 'unsafe_eligible': row['unsafe_action_eligible_events'],
        'false_intervention_eligible': row['false_intervention_eligible_events']}}

def _mechanisms(episode):
    rows=episode.pipeline_results
    return {'direct_threat_evidence':sum(r.threat_assessment.status.value=='DIRECT_EVIDENCE' for r in rows),
      'persistent_unexplained_drift':sum(r.drift_assessment.status.value=='UNEXPLAINED_PERSISTENT_DRIFT' for r in rows),
      'known_regime_change':sum(r.drift_assessment.status.value=='KNOWN_REGIME_CHANGE' for r in rows),
      'assurance_restrictions':sum(bool(r.assurance_assessment.restrictions) for r in rows),
      'already_restricted_upstream':sum(r.assurance_assessment.causal_effect.value=='ALREADY_RESTRICTED_UPSTREAM' for r in rows),
      'adaptation_applications':sum(r.adaptation_decision.status.value=='APPLIED' for r in rows),
      'adapted_reference_usage':sum(r.behavioral_reference_used is not None for r in rows),
      'governance_vetoes':sum(r.governance_decision.status.value=='VETOED' for r in rows),
      'trust': {'initial':rows[0].trust_assessment.composite_trust,'final':rows[-1].trust_assessment.composite_trust,
                'minimum':min(r.trust_assessment.composite_trust for r in rows),'maximum':max(r.trust_assessment.composite_trust for r in rows)}}

def evaluate(seeds=VALIDATION_SEEDS):
    streams={}
    for s in SCENARIOS:
      for seed in seeds:
        g=EventGenerator(seed, observable_state=True); run=g.create_run(s,event_count(s)); streams[s,seed]=(run,g.generate(s,event_count(s),run))
    raw={}
    for cfg in AblationConfiguration:
      for (s,seed),(run,events) in streams.items():
        ep=create_ablation_pipeline(cfg).run_episode(events,scenario_reference=run.experiment_id,seed=seed)
        raw[cfg.value,s,str(seed)]={'metrics':_metrics(ep,events),'mechanisms':_mechanisms(ep)}
    table_b={}
    for cfg in AblationConfiguration:
      for s in SCENARIOS:
        vals={m:[raw[cfg.value,s,str(seed)]['metrics'][m] for seed in seeds] for m in METRICS}
        table_b[f'{cfg.value}:{s}']={m:summary(v) for m,v in vals.items()}
    paired={}
    for left,right,scenario,metric in [('FULL_STATIC','NO_ASSURANCE','S7','unsafe_action_rate'),('FULL_STATIC','NO_DRIFT','S7','unsafe_action_rate'),('FULL_STATIC','NO_TRUST','S7','unsafe_action_rate'),('FULL_ADAPTIVE','NO_ADAPT','S8','proposal_review_burden'),('FULL_STATIC','RULE_BASED','S7','unsafe_action_rate')]:
      paired[f'{left}_vs_{right}:{scenario}:{metric}']=paired_difference([raw[left,scenario,str(x)]['metrics'][metric] for x in seeds],[raw[right,scenario,str(x)]['metrics'][metric] for x in seeds])
    return {'experiment_version':'milestone8d-publication-ablation-v1','seeds':list(seeds),'replication_unit':'seed','events_not_independent':True,
      'configuration_definitions':{c.value:{'differs_from_full':list(SPECS[c].differs_from_full),'fingerprint':SPECS[c].fingerprint} for c in AblationConfiguration},
      'no_governance':{'valid':False,'reason':'Would remove the governance authorization artifact required by execution integrity; not run.'},
      'scenario_fingerprints':{s:fingerprint(get_scenario_evaluation_metadata(s,event_count(s)).to_dict()) for s in SCENARIOS},
      'event_stream_fingerprints':{f'{s}:{seed}':event_stream_fingerprint(events) for (s,seed),(_,events) in streams.items()},
      'raw_seed_level':{'|'.join(k):v for k,v in raw.items()},'table_b_per_scenario':table_b,'paired_comparisons':paired,
      'performance':{'status':'EXCLUDED_FROM_SEMANTIC_ARTIFACT','note':'Wall-clock timing is nondeterministic and not used for scientific comparison.'},
      'limitations':['No governance ablation is run because it would weaken execution-integrity protection.','No p-values are reported; seed-level summaries are exploratory.','S7 dynamic trust remains non-causal under frozen evidence.']}

def main():
 p=argparse.ArgumentParser();p.add_argument('--publication',action='store_true');p.add_argument('--output',type=Path,default=Path('results/milestone8d-ablation-validation.json'));a=p.parse_args()
 r=evaluate(PUBLICATION_SEEDS if a.publication else VALIDATION_SEEDS);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');print(f"Evaluated {len(r['seeds'])} seeds across {len(AblationConfiguration)} configurations.")
if __name__=='__main__':main()
