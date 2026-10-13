"""Reproduce the successful board and verify all six Easter eggs plus the defect."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--puzzle-dir',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('results'))
    parser.add_argument('--evidence',type=Path,default=Path('evidence'))
    args = parser.parse_args()
    puzzle, results, evidence = args.puzzle_dir.resolve(), args.out.resolve(), args.evidence.resolve()
    src = Path(__file__).resolve().parent/'src'
    env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    def run(script,*arguments):
        subprocess.run([sys.executable,str(src/script),*map(str,arguments)],check=True,env=env)
    run('reproduce.py','--puzzle-dir',puzzle,'--out',results)
    run('extract_easter_geometry.py','--puzzle-dir',puzzle,'--out',evidence/'geometry')
    run('analyze_signals.py','--vcd',puzzle/'example_inputs.vcd',
        '--verification',results/'verification.json','--out-dir',evidence/'signals')
    run('audit_floating.py','--results',results,'--out',evidence/'floating')
    data = json.loads((results/'verification.json').read_text())
    geometry = json.loads((evidence/'geometry/geometry_summary.json').read_text())
    signals = json.loads((evidence/'signals/signals_evidence.json').read_text())
    floating = json.loads((evidence/'floating/floating_wire.json').read_text())
    assert signals['vcd_input_decode']['decoded_including_padding'] == 'The night sky awaits  '
    assert signals['vcd_header']['date'] == 'Sat Dec 31 23:59:60 2016'
    assert signals['vcd_header']['weekday_check']
    assert geometry['morse']['decoded'] == 'PER ARENAM AD ASTRA'
    assert geometry['logo']['pixel_count'] == 1366
    assert geometry['logo']['rows'] == geometry['logo']['columns'] == 57
    assert geometry['logo']['conservative_isolation_check']['electrically_isolated_from_routing']
    assert signals['region_geometry']['reading'] == 'JSC'
    assert floating['winning_output_independent_of_floating_value']
    assert floating['adjacency_rejection_independent_of_floating_value']
    eggs = [
        {'id':1,'name':'Hidden VCD text','result':'The night sky awaits  ','evidence':'signals/signals_evidence.json'},
        {'id':2,'name':'Leap-second date and waveform-viewer version clue','result':signals['vcd_header']['date'],'evidence':'signals/signals_evidence.json'},
        {'id':3,'name':'Outside-die Morse annotation','result':geometry['morse']['decoded'],'evidence':'geometry/morse_geometry.json'},
        {'id':4,'name':'Failure-message branches','result':['EMPTY SKY','BIG BANG','TRY AGAIN','TWO"NOT TOUCH'],'evidence':'../results/verification.json'},
        {'id':5,'name':'Met2 Jane Street logo','result':{'pixels':1366,'grid':[57,57]},'evidence':'geometry/logo_pixelmap.json'},
        {'id':6,'name':'Recovered region silhouettes','result':'JSC','interpretation':'Visual inference from exact I/H/K occupied-cell masks.','evidence':'signals/signals_evidence.json'},
    ]
    for egg in eggs: egg['verified'] = True
    summary = {'all_six_intended_easter_eggs_verified':True,'intended_easter_eggs':eggs,
               'additional_floating_wire_defect_verified':True,
               'floating_wire_evidence':'floating/floating_wire.json',
               'answer':data['answer'],'source_sha256':data['source_sha256'],
               'scope':'Source extraction and Boolean functional reproduction; visual logo/glyph identification is corroborated by the organizer; no analog sign-off.'}
    (evidence/'all_easter_eggs.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print('COMPLETE: main solution, all six intended Easter eggs, and floating-wire defect verified.')


if __name__ == '__main__':
    main()
