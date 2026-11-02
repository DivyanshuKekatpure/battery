"""One-time, user-authorized archive migration; no raw downloads are moved."""
import csv,hashlib,shutil
from pathlib import Path
from .common import ROOT


def main():
    marker=ROOT/'legacy/archive_files.csv'
    if marker.exists():raise SystemExit('Archive already completed; refusing to move active artifacts again.')
    jobs=[]
    old_scripts=['analyze.py','build_parameters.py','extract_full.py','extract_summary.py','financial.py','financial_figures.py','inspect_structure.py','make_reports.js','simulate.py','svgplot.py']
    for name in old_scripts:jobs.append((ROOT/'scripts'/name,ROOT/'legacy/lfp/scripts'/name))
    jobs.append((ROOT/'README.md',ROOT/'legacy/lfp/README.md'))
    for p in (ROOT/'outputs').iterdir():
        if p.name not in ['kit','kit_audit','isu_audit','reports']:jobs.append((p,ROOT/'legacy/lfp/outputs'/p.name))
    for name in ['Preliminary_Methods_and_Results.docx','Financial_Impacts.docx','Rough_Draft.docx']:
        jobs.append((ROOT/'outputs/reports'/name,ROOT/'legacy/lfp/outputs/reports'/name))
    jobs.append((ROOT/'outputs/isu_audit',ROOT/'legacy/isu/outputs/isu_audit'))
    jobs.append((ROOT/'scripts/audit_isu.py',ROOT/'legacy/isu/scripts/audit_isu.py'))
    records=[]
    for source,dest in jobs:
        if not source.exists():raise FileNotFoundError(source)
        if dest.exists():raise FileExistsError(dest)
        files=list(source.rglob('*')) if source.is_dir() else [source]
        for f in files:
            if f.is_file():
                relative=f.relative_to(source) if source.is_dir() else None
                target=dest/relative if relative is not None else dest
                records.append({'original_path':str(f.relative_to(ROOT)),'archive_path':str(target.relative_to(ROOT)),
                                'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size})
    # The validated draft gate precedes any archive operation.
    assert (ROOT/'outputs/kit/acceptance_checks.json').exists()
    for source,dest in jobs:dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(source),str(dest))
    with marker.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    for r in records:assert hashlib.sha256((ROOT/r['archive_path']).read_bytes()).hexdigest()==r['sha256']
    (ROOT/'legacy/README.md').write_text('# Historical analyses\n\nlfp/ contains the former LFP extraction, simulation, analysis and reports. isu/ contains the alternative dataset audit. archive_files.csv records original paths and SHA256 hashes. These are historical artifacts; their claims are not current KIT findings. Raw data/ and data2/ are unchanged. Historical decisions remain in docs/old_decision_log.md.\n')
    print(f'Archived and hash-verified {len(records)} files.')

if __name__=='__main__':main()
