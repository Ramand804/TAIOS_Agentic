import argparse, json
from pathlib import Path
from evaluation.evaluate_v2_agentic import evaluate

def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,default=Path('analysis/v2/v2_agentic_validation.json')); args=parser.parse_args()
 result=evaluate(); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
 print(args.output)
if __name__=='__main__': main()
