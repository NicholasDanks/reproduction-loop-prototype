#!/usr/bin/env python3
"""Batch assessment of unevaluated MNSC packages using v3.1 instrument.

Reads master_matrix.csv to find already-assessed packages,
then scores all remaining package directories on 15 Tier A items.

Usage:
    python3 batch_assess_new.py [--limit N] [--dry-run]
"""

import csv
import os
import re
import sys
import json
from pathlib import Path

# Tier A items and their scoring logic
TIER_A_ITEMS = [
    'A1.1', 'A1.2', 'A2.1', 'A2.2', 'A2.3',
    'A3.1', 'A3.2', 'A4.1', 'A4.2', 'A5.1',
    'A5.2', 'A6.1', 'A6.2', 'A7.1', 'A7.2'
]

def find_files(pkg_dir):
    """Catalog all files in package."""
    files = []
    for root, dirs, fnames in os.walk(pkg_dir):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in fnames:
            if not f.startswith('.'):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, pkg_dir)
                ext = os.path.splitext(f)[1].lower()
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                files.append({'path': full, 'rel': rel, 'name': f, 'ext': ext, 'size': size})
    return files

def detect_language(files):
    """Detect primary programming language."""
    ext_counts = {}
    code_exts = {'.py': 'Python', '.r': 'R', '.do': 'Stata', '.m': 'MATLAB',
                 '.jl': 'Julia', '.sas': 'SAS', '.f90': 'Fortran', '.f': 'Fortran',
                 '.ipynb': 'Python', '.sps': 'SPSS', '.gauss': 'GAUSS',
                 '.ox': 'Ox', '.src': 'GAUSS'}
    for f in files:
        lang = code_exts.get(f['ext'])
        if lang:
            ext_counts[lang] = ext_counts.get(lang, 0) + 1
    if not ext_counts:
        return 'Unknown'
    return max(ext_counts, key=ext_counts.get)

def has_stochastic(files):
    """Check if package likely has stochastic operations."""
    stochastic_patterns = [
        r'random', r'seed', r'sample\(', r'rnorm', r'runif', r'np\.random',
        r'simulate', r'bootstrap', r'permut', r'monte.carlo', r'set\.seed',
        r'Random', r'SEED'
    ]
    for f in files:
        if f['ext'] in ('.py', '.r', '.do', '.m', '.jl', '.sas', '.ipynb'):
            try:
                with open(f['path'], 'r', errors='ignore') as fh:
                    content = fh.read(50000)  # First 50KB
                    for pat in stochastic_patterns:
                        if re.search(pat, content, re.IGNORECASE):
                            return True
            except:
                pass
    return False

def score_package(pkg_dir, files):
    """Score a package on 15 Tier A items. Returns dict of scores."""
    scores = {}
    lang = detect_language(files)

    code_files = [f for f in files if f['ext'] in
                  ('.py', '.r', '.do', '.m', '.jl', '.sas', '.f90', '.f', '.ipynb', '.sps', '.gauss', '.ox', '.src')]
    data_files = [f for f in files if f['ext'] in
                  ('.csv', '.dta', '.xlsx', '.xls', '.sav', '.rds', '.rdata', '.mat', '.sas7bdat', '.npy', '.json', '.parquet', '.feather', '.h5', '.hdf5', '.pickle', '.pkl')]
    readme_files = [f for f in files if re.match(r'readme', f['name'], re.IGNORECASE)]

    # A1.1: Code publicly accessible (all are from Dataverse = Partial)
    scores['A1.1'] = 0.5

    # A1.2: Open license
    license_files = [f for f in files if re.match(r'licen[sc]e', f['name'], re.IGNORECASE)]
    if license_files:
        scores['A1.2'] = 1.0
    else:
        # Check README for license mention
        for rf in readme_files:
            try:
                with open(rf['path'], 'r', errors='ignore') as fh:
                    content = fh.read(10000).lower()
                    if 'license' in content or 'licence' in content:
                        scores['A1.2'] = 0.5
                        break
            except:
                pass
        if 'A1.2' not in scores:
            scores['A1.2'] = 0.0

    # A2.1: Data included or linked
    if data_files:
        total_data_size = sum(f['size'] for f in data_files)
        if total_data_size > 1000:  # More than 1KB of data
            scores['A2.1'] = 1.0
        else:
            scores['A2.1'] = 0.5
    else:
        # Check for data download instructions
        scores['A2.1'] = 0.0
        for rf in readme_files:
            try:
                with open(rf['path'], 'r', errors='ignore') as fh:
                    content = fh.read(10000).lower()
                    if 'download' in content or 'available' in content or 'request' in content:
                        scores['A2.1'] = 0.5
                        break
            except:
                pass

    # A2.2: Data format documented
    codebook = [f for f in files if re.search(r'codebook|dictionary|variable|metadata', f['name'], re.IGNORECASE)]
    if codebook:
        scores['A2.2'] = 1.0
    elif readme_files:
        scores['A2.2'] = 0.5  # Assume README has some data description
    else:
        scores['A2.2'] = 0.0

    # A2.3: Data completeness
    if not code_files:
        scores['A2.3'] = ''  # N/A
    elif data_files and len(data_files) >= 1:
        scores['A2.3'] = 0.5  # Partial by default; can't verify completeness automatically
    else:
        scores['A2.3'] = 0.0

    # A3.1: Language and version specified
    scores['A3.1'] = 0.0
    for rf in readme_files:
        try:
            with open(rf['path'], 'r', errors='ignore') as fh:
                content = fh.read(10000)
                # Look for version numbers
                if re.search(r'(python|stata|matlab|R|julia)\s*\d+\.\d+', content, re.IGNORECASE):
                    scores['A3.1'] = 1.0
                    break
                elif re.search(r'(python|stata|matlab|R version|julia)', content, re.IGNORECASE):
                    scores['A3.1'] = 0.5
                    break
        except:
            pass
    # Check code files for version commands
    if scores['A3.1'] == 0.0:
        for cf in code_files[:5]:
            try:
                with open(cf['path'], 'r', errors='ignore') as fh:
                    head = fh.read(2000)
                    if re.search(r'version\s+\d+', head, re.IGNORECASE):
                        scores['A3.1'] = 0.5
                        break
            except:
                pass

    # A3.2: Dependencies declared
    dep_files = [f for f in files if f['name'].lower() in
                 ('requirements.txt', 'environment.yml', 'conda.yml', 'pipfile', 'pipfile.lock',
                  'setup.py', 'setup.cfg', 'pyproject.toml', 'description', 'renv.lock',
                  'project.toml', 'manifest.toml', 'packages.txt')]
    if dep_files:
        scores['A3.2'] = 0.5  # File exists; assume partial (can't verify pinning)
    else:
        # Check for ssc install or library() calls documented in README
        scores['A3.2'] = 0.0
        for rf in readme_files:
            try:
                with open(rf['path'], 'r', errors='ignore') as fh:
                    content = fh.read(10000).lower()
                    if 'install' in content or 'package' in content or 'library' in content:
                        scores['A3.2'] = 0.5
                        break
            except:
                pass

    # A4.1: README present with substance
    if readme_files:
        # Check if README has substance
        rf = readme_files[0]
        try:
            size = rf['size']
            if size > 500:
                scores['A4.1'] = 1.0
            elif size > 100:
                scores['A4.1'] = 0.5
            else:
                scores['A4.1'] = 0.5
        except:
            scores['A4.1'] = 0.5
    else:
        scores['A4.1'] = 0.0

    # A4.2: Code documentation patterns
    if not code_files:
        scores['A4.2'] = ''
    else:
        total_lines = 0
        comment_lines = 0
        for cf in code_files[:10]:  # Sample up to 10 files
            try:
                with open(cf['path'], 'r', errors='ignore') as fh:
                    for line in fh:
                        total_lines += 1
                        stripped = line.strip()
                        if stripped.startswith('#') or stripped.startswith('*') or stripped.startswith('//') or stripped.startswith('%'):
                            comment_lines += 1
            except:
                pass
        if total_lines > 0:
            ratio = comment_lines / total_lines
            if ratio > 0.10:
                scores['A4.2'] = 1.0
            elif ratio > 0.05:
                scores['A4.2'] = 0.5
            else:
                scores['A4.2'] = 0.0
        else:
            scores['A4.2'] = 0.0

    # A5.1: Code modularized
    if len(code_files) >= 3:
        scores['A5.1'] = 0.5  # Multiple files = partial
        # Check for functions
        has_functions = False
        for cf in code_files[:5]:
            try:
                with open(cf['path'], 'r', errors='ignore') as fh:
                    content = fh.read(20000)
                    if re.search(r'def \w+\(|function\s*\(|program\s+define|function\s+\[', content):
                        has_functions = True
                        break
            except:
                pass
        if has_functions and len(code_files) >= 3:
            scores['A5.1'] = 1.0
    elif len(code_files) == 2:
        scores['A5.1'] = 0.5
    elif len(code_files) == 1:
        scores['A5.1'] = 0.0
    else:
        scores['A5.1'] = 0.0

    # A5.2: No hardcoded absolute paths
    abs_path_count = 0
    for cf in code_files:
        try:
            with open(cf['path'], 'r', errors='ignore') as fh:
                content = fh.read()
                # Windows paths
                abs_path_count += len(re.findall(r'["\'][A-Z]:\\', content))
                # Unix absolute paths (excluding shebangs and common system paths)
                abs_path_count += len(re.findall(r'["\'](/Users/|/home/|/scratch/|/data/)', content))
        except:
            pass
    if abs_path_count == 0:
        scores['A5.2'] = 1.0
    elif abs_path_count <= 3:
        scores['A5.2'] = 0.5
    else:
        scores['A5.2'] = 0.0

    # A6.1: Random seeds set
    if not has_stochastic(files):
        scores['A6.1'] = ''  # N/A
    else:
        has_seed = False
        for cf in code_files:
            try:
                with open(cf['path'], 'r', errors='ignore') as fh:
                    content = fh.read()
                    if re.search(r'set\.seed|np\.random\.seed|random\.seed|set seed|srand|Random\.seed', content, re.IGNORECASE):
                        has_seed = True
                        break
            except:
                pass
        scores['A6.1'] = 1.0 if has_seed else 0.0

    # A6.2: Outputs generated by code
    output_files = [f for f in files if f['ext'] in ('.png', '.pdf', '.eps', '.svg', '.jpg', '.tex', '.html', '.xlsx', '.xls', '.csv')
                    and any(kw in f['rel'].lower() for kw in ('output', 'result', 'figure', 'table', 'plot', 'fig'))]
    if output_files:
        scores['A6.2'] = 0.5  # Pre-generated outputs exist
    else:
        # Check if code has write/save commands
        has_save = False
        for cf in code_files[:10]:
            try:
                with open(cf['path'], 'r', errors='ignore') as fh:
                    content = fh.read(20000)
                    if re.search(r'savefig|write\.csv|outreg|esttab|stargazer|ggsave|exportgraphics|print\(.*file|save.*\.png|save.*\.pdf', content, re.IGNORECASE):
                        has_save = True
                        break
            except:
                pass
        if has_save:
            scores['A6.2'] = 1.0
        else:
            scores['A6.2'] = 0.5  # Code likely produces screen output

    # A7.1: Tables/figures covered by code
    if code_files:
        # Check for table/figure references in code
        has_mapping = False
        for cf in code_files[:10]:
            try:
                with open(cf['path'], 'r', errors='ignore') as fh:
                    content = fh.read(20000)
                    if re.search(r'[Tt]able\s*\d|[Ff]igure\s*\d|[Tt]ab\s*\d|[Ff]ig\s*\d', content):
                        has_mapping = True
                        break
            except:
                pass
        if has_mapping:
            scores['A7.1'] = 1.0
        else:
            scores['A7.1'] = 0.5  # Code exists but mapping unclear
    else:
        scores['A7.1'] = 0.0

    # A7.2: Sample sizes documented
    has_n = False
    for cf in code_files[:10]:
        try:
            with open(cf['path'], 'r', errors='ignore') as fh:
                content = fh.read(20000)
                if re.search(r'assert.*[Nn]|count|di\s+_N|nrow|len\(|\.shape|sample.size|observations', content, re.IGNORECASE):
                    has_n = True
                    break
        except:
            pass
    if has_n:
        scores['A7.2'] = 0.5
    else:
        scores['A7.2'] = 0.0

    return scores, lang

def compute_tier_a(scores):
    """Compute Tier A percentage from item scores."""
    applicable = []
    for item in TIER_A_ITEMS:
        val = scores.get(item, '')
        if val != '' and val is not None:
            applicable.append(float(val))
    if not applicable:
        return None
    return round(sum(applicable) / len(applicable) * 100, 1)

def main():
    limit = None
    dry_run = False
    for arg in sys.argv[1:]:
        if arg == '--dry-run':
            dry_run = True
        elif arg.startswith('--limit'):
            limit = int(arg.split('=')[1]) if '=' in arg else int(sys.argv[sys.argv.index(arg)+1])

    # Load already assessed
    assessed = set()
    existing_rows = []
    with open('claude_working/master_matrix.csv') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            assessed.add(row['package'])
            existing_rows.append(row)

    print(f"Already assessed: {len(assessed)}")

    # Find all package directories
    batch_dirs = [
        ('replicatino packages MNSC', 'MNSC_orig'),
        ('new_replication_packages_MNSC', 'MNSC_new'),
        ('new_replication_packages_MNSC2', 'MNSC2'),
        ('new_replication_packages_MNSC3', 'MNSC3'),
        ('new_replication_packages_MNSC4', 'MNSC4'),
        ('new_replication_packages_MNSC5', 'MNSC5'),
        ('new_replication_packages_MNSC6', 'MNSC6'),
        ('new_replication_packages_MNSC7_unpacked', 'MNSC7'),
    ]

    to_assess = []
    for batch_path, batch_name in batch_dirs:
        if not os.path.isdir(batch_path):
            continue
        for d in sorted(os.listdir(batch_path)):
            full = os.path.join(batch_path, d)
            if os.path.isdir(full) and re.match(r'\d{2}-\d{4,5}', d) and d not in assessed:
                to_assess.append((d, full, batch_name))

    print(f"To assess: {len(to_assess)}")

    if limit:
        to_assess = to_assess[:limit]
        print(f"Limited to: {limit}")

    if dry_run:
        print("\nDry run - would assess:")
        for pkg_id, pkg_path, batch in to_assess[:20]:
            print(f"  {pkg_id} ({batch})")
        if len(to_assess) > 20:
            print(f"  ... and {len(to_assess) - 20} more")
        return

    # Assess each package
    new_rows = []
    for i, (pkg_id, pkg_path, batch) in enumerate(to_assess):
        files = find_files(pkg_path)
        if not files:
            continue

        scores, lang = score_package(pkg_path, files)
        tier_a = compute_tier_a(scores)

        if tier_a is None:
            continue

        row = {
            'package': pkg_id,
            'source': batch,
            'report_version': 'v3.1',
            'tier_a_pct': tier_a,
            'strict_pct': '',
            'generous_pct': '',
        }
        for item in TIER_A_ITEMS:
            row[item] = scores.get(item, '')

        new_rows.append(row)

        if (i + 1) % 50 == 0:
            print(f"  Assessed {i+1}/{len(to_assess)}... (last: {pkg_id} = {tier_a}%)")

    print(f"\nAssessed {len(new_rows)} new packages")

    if new_rows:
        # Compute stats
        tier_a_vals = [float(r['tier_a_pct']) for r in new_rows if r['tier_a_pct']]
        import numpy as np
        arr = np.array(tier_a_vals)
        print(f"New batch: mean={arr.mean():.1f}%, median={np.median(arr):.1f}%, SD={arr.std():.1f}%")
        print(f"Range: {arr.min():.1f}% to {arr.max():.1f}%")

    # Write updated master_matrix
    all_rows = existing_rows + new_rows
    with open('claude_working/master_matrix.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        for row in all_rows:
            # Remove any None keys
            clean_row = {k: v for k, v in row.items() if k is not None}
            writer.writerow(clean_row)

    print(f"Master matrix updated: {len(all_rows)} total rows")

if __name__ == '__main__':
    main()
