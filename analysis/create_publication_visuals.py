"""Create Phase 2B aggregate visuals from frozen publication data only."""
import json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path('publication'); FIG=ROOT/'figures'; TAB=ROOT/'tables'; CAP=ROOT/'captions'; MAP=ROOT/'source_mapping'
SRC=Path('results/taios-publication-experiment-v1.json')
def save(fig,name):
    fig.tight_layout(); fig.savefig(FIG/(name+'.pdf')); fig.savefig(FIG/(name+'.png'),dpi=300); plt.close(fig)
def main():
    for p in (FIG,TAB,CAP,MAP): p.mkdir(parents=True,exist_ok=True)
    x=json.loads(SRC.read_text()); raw=x['raw_seed_level']
    configs=['FULL_STATIC','NO_ASSURANCE','NO_DRIFT','NO_TRUST','RULE_BASED']
    s7={c:raw[f'{c}|S7|42'] for c in configs}
    fig,ax=plt.subplots(figsize=(7,3.6)); vals=[100*s7[c]['metrics']['unsafe_action_rate'] for c in configs]
    bars=ax.bar(configs,vals,color=['#2b6cb0','#c53030','#c53030','#718096','#c53030']);ax.set_ylabel('Unsafe-action rate (%)');ax.set_ylim(0,110);ax.tick_params(axis='x',rotation=25)
    for b,c in zip(bars,configs): ax.text(b.get_x()+b.get_width()/2,b.get_height()+2,f"{int(round(vals[configs.index(c)])) if vals[configs.index(c)]!=4 else 4}%\n{s7[c]['metrics']['denominators']['unsafe_eligible']} eligible",ha='center',fontsize=8)
    save(fig,'fig04_s7_unsafe_ablation')
    fig,ax=plt.subplots(figsize=(7,3.6)); trust=[s7['FULL_STATIC']['mechanisms']['trust']['initial'],s7['FULL_STATIC']['mechanisms']['trust']['final']]; ax.plot([1,50],trust,label='Dynamic trust',marker='o');ax.plot([1,50],[.8,.8],'--',label='NoTrust fixed 0.80');ax.set(xlabel='S7 event position (endpoints)',ylabel='Trust',ylim=(.79,.83));ax.legend();save(fig,'fig05_s7_trust')
    (TAB/'table04_s7_causal_ablation.json').write_text(json.dumps(s7,sort_keys=True,indent=2)+'\n')
    (TAB/'table05_s7_paired_analysis.json').write_text(json.dumps(x['paired_comparisons'],sort_keys=True,indent=2)+'\n')
    (CAP/'fig04_s7_unsafe_ablation.md').write_text('**Figure 4.** Controlled S7 unsafe-action rates. Labels retain eligible-event denominators; this is synthetic scenario evidence, not real-world attack prevention.\n')
    (CAP/'fig05_s7_trust.md').write_text('**Figure 5.** S7 trust endpoints: dynamic trust increases while fixed NoTrust remains 0.80 and final actions are identical.\n')
    (MAP/'README.md').write_text('# Traceability\n\nFigures 4--5 and Tables 4--5 derive from `results/taios-publication-experiment-v1.json`, fields `raw_seed_level` and `paired_comparisons`. Event-level trajectory figures are unavailable from the permitted aggregate figure-data files and were not fabricated.\n')
if __name__=='__main__': main()
