"""Derive deterministic table and figure data from the frozen 8D artifact only."""
import json
from pathlib import Path

SOURCE = Path('results/taios-publication-experiment-v1.json')
TABLES = Path('results/tables'); FIGURES = Path('results/figure_data')

def write(path, value): path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
def main():
 x=json.loads(SOURCE.read_text()); raw=x['raw_seed_level']
 TABLES.mkdir(parents=True,exist_ok=True); FIGURES.mkdir(parents=True,exist_ok=True)
 by_cfg={c:{k:v for k,v in raw.items() if k.startswith(c+'|')} for c in x['configuration_definitions']}
 write(TABLES/'TABLE_A_OVERALL_CONFIGURATION_METRICS.json', by_cfg)
 write(TABLES/'TABLE_B_PER_SCENARIO_METRICS.json', x['table_b_per_scenario'])
 write(TABLES/'TABLE_C_S7_CAUSAL_ABLATION.json',{c:{k:v for k,v in raw.items() if k.startswith(c+'|S7|')} for c in ('FULL_STATIC','FULL_ADAPTIVE','NO_ASSURANCE','NO_DRIFT','NO_TRUST','RULE_BASED')})
 write(TABLES/'TABLE_D_S8_ADAPTATION.json',{c:{k:v for k,v in raw.items() if k.startswith(c+'|S8|')} for c in ('FULL_STATIC','FULL_ADAPTIVE','NO_ADAPT')})
 write(TABLES/'TABLE_E_S9_RECOVERY.json',{c:{k:v for k,v in raw.items() if k.startswith(c+'|S9|')} for c in x['configuration_definitions']})
 write(TABLES/'TABLE_F_MECHANISM_COUNTS.json',{k:v['mechanisms'] for k,v in raw.items()})
 write(TABLES/'TABLE_G_PAIRED_COMPARISONS.json',x['paired_comparisons'])
 for name, scenarios in {'FIGURE_S7_VALUE_DRIFT':['S7'],'FIGURE_S7_ASSURANCE_ACTIONS':['S7'],'FIGURE_S7_UNSAFE_ABLATION':['S7'],'FIGURE_S7_TRUST_NOTRUST':['S7'],'FIGURE_S8_STATIC_ADAPTIVE':['S8'],'FIGURE_S9_RECOVERY':['S9']}.items():
  write(FIGURES/(name+'.json'),{k:v for k,v in raw.items() if any('|'+s+'|' in k for s in scenarios)})
if __name__=='__main__': main()
