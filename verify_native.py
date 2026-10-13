"""Optional independent native gdstk comparison. Install gdstk first."""
import argparse
import json
from pathlib import Path
import sys

# Import the installed implementation before adding the bundled subset reader.
import gdstk
assert getattr(gdstk,'__version__',None), 'Native gdstk is required.'
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
import extract2

parser = argparse.ArgumentParser()
parser.add_argument('--puzzle-dir',type=Path,required=True)
parser.add_argument('--netlist',type=Path,default=Path('results/netlist.json'))
args = parser.parse_args()
native = extract2.run(str(args.puzzle_dir/'puzzle.gds'),'puzzle')
expected = json.loads(args.netlist.read_text())
assert json.loads(json.dumps(native)) == expected
print('Native gdstk',gdstk.__version__,'and bundled reader produce identical extracted connectivity.')
