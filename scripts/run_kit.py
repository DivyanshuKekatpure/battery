"""Run all active KIT stages. Usage: .venv/bin/python -m scripts.run_kit"""
import os,subprocess,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    os.chdir(ROOT)
    env=dict(os.environ,VECLIB_MAXIMUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MPLCONFIGDIR='/tmp/kit-matplotlib')
    stages=[['scripts/audit_kit.py'],['-m','scripts.kit.prepare'],['-m','unittest','discover','-s','tests','-v'],
            ['-m','scripts.kit.analysis'],['-m','scripts.kit.finance'],['-m','scripts.kit.figures'],
            ['-m','scripts.kit.reports'],['-m','scripts.kit.validate']]
    for stage in stages:
        print('Running', ' '.join(stage),flush=True)
        subprocess.run([sys.executable,*stage],check=True,env=env)
    # Preserve old reports until the one-time migration has archived them.
    marker=ROOT/'legacy'/'archive_files.csv'
    if not marker.exists():
        print('Validated drafts ready. Complete the one-time legacy archive before publishing.',flush=True)
        return
    for name in ['Preliminary_Methods_and_Results','Financial_Impacts']:
        for ext in ['docx','md']:
            source=ROOT/'outputs/kit/report_drafts'/f'{name}.{ext}'
            target=ROOT/'outputs/reports'/f'{name}.{ext}'
            if ext=='md':target.write_text(source.read_text().replace('](../figures/','](../kit/figures/'))
            else:shutil.copy2(source,target)
    print('Published both validated reports.',flush=True)

if __name__=='__main__':main()
