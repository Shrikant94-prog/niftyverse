"""Read-only structural checks for the niftyverse specification bundle (stdlib only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


def slug(text: str) -> str:
    text = re.sub(r'[`*_]', '', text).lower()
    return re.sub(r'[^\w\- ]', '', text).replace(' ', '-')


def without_fences(text: str) -> str:
    return re.sub(r'^```[^\n]*\n[\s\S]*?^```\s*$', '', text, flags=re.M)


def anchors(text: str) -> set[str]:
    text = without_fences(text)
    found = set(re.findall(r'<a id="([^"]+)">', text))
    counts: dict[str, int] = {}
    for heading in re.findall(r'^#{1,6} (.+)$', text, re.M):
        key = slug(heading)
        count = counts.get(key, 0)
        found.add(key if count == 0 else f'{key}-{count}')
        counts[key] = count + 1
    return found


def link_errors(files: dict[str, str]) -> list[str]:
    errors = []
    for name, body in files.items():
        if not name.endswith('.md'):
            continue
        for match in re.finditer(r'\[[^\]\n]+\]\(([^)\n]+)\)', without_fences(body)):
            url = match[1].strip('<>')
            if url.startswith(('http:', 'https:', 'mailto:')):
                continue
            raw_path, _, anchor = url.partition('#')
            target = (Path(name).parent / unquote(raw_path)) if raw_path else Path(name)
            # Normalize relative segments without touching the filesystem.
            parts: list[str] = []
            for part in target.parts:
                if part == '..':
                    if parts:
                        parts.pop()
                    else:
                        errors.append(f'{name}: link escapes bundle: {url}')
                elif part not in {'.', ''}:
                    parts.append(part)
            key = '/'.join(parts)
            if key not in files:
                errors.append(f'{name}: missing target: {url}')
            elif anchor and unquote(anchor) not in anchors(files[key]):
                errors.append(f'{name}: missing anchor: {url}')
    return errors


def id_errors(actual: set[str], expected: set[str], label: str) -> list[str]:
    return ([f'{label}: missing {x}' for x in sorted(expected - actual)]
            + [f'{label}: unexpected {x}' for x in sorted(actual - expected)])


def dependency_errors(order: list[str], deps: dict[str, list[str]]) -> list[str]:
    errors = []
    if len(order) != 23 or set(order) != {f'{n:02}' for n in range(23)}:
        errors.append('Phase order must contain 00–22 exactly once.')
    positions = {phase: i for i, phase in enumerate(order)}
    for phase, requirements in deps.items():
        for dep in requirements:
            if dep not in positions or phase not in positions or positions[dep] >= positions[phase]:
                errors.append(f'Invalid dependency order: {phase} depends on {dep}')
    return errors


def self_test() -> None:
    assert not link_errors({'a.md': '[ok](b.md#part)', 'b.md': '<a id="part"></a>\n## Part'})
    assert link_errors({'a.md': '[bad](missing.md)'})
    assert link_errors({'a.md': '[bad](b.md#absent)', 'b.md': '# Present'})
    assert id_errors({'A'}, {'A', 'B'}, 'test')
    assert not id_errors({'A', 'B'}, {'A', 'B'}, 'test')
    assert dependency_errors([f'{n:02}' for n in range(23)], {'00': ['01']})
    assert not dependency_errors([f'{n:02}' for n in range(23)], {'01': ['00']})
    print('Negative/positive fixtures: link, anchor, omitted ID, and dependency checks passed.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true', help='Check delivered static-document fingerprints too.')
    parser.add_argument('--self-test', action='store_true', help='Exercise checker fixtures before bundle checks.')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'docs/BASELINE.json').read_text(encoding='utf-8'))
    files = {p.relative_to(root).as_posix(): p.read_text(encoding='utf-8')
             for p in root.rglob('*') if p.is_file() and p.suffix in {'.md', '.json', '.py'}}
    markdown = {k: v for k, v in files.items() if k.endswith('.md')}
    errors = link_errors(files)
    phase_body = '\n'.join(v for k, v in markdown.items() if re.fullmatch(r'docs/phases/\d\d.md', k))
    ids = manifest['retained_ids']
    actual_outcomes = set(re.findall(r'^## (NV-\d\d-\d\d)$', phase_body, re.M))
    actual_acs = set(re.findall(r'\*\*(NV-\d\d-\d\d-AC\d+):', phase_body))
    errors += id_errors(actual_outcomes, set(ids['outcomes']), 'outcome')
    errors += id_errors(actual_acs, set(ids['acceptance']), 'acceptance')
    for label, text, pattern in [
        ('requirements', files['docs/specs/requirements.md'], r'\b(?:CORE|NET|STORE|ID|UNI|EQ|ETF|IDX|DER|REP|CORP|FUND|OWN|GLOB|BUILD|TIME|RES|API|UX|QA|DOC)-\d\d\b'),
        ('decisions', files['docs/specs/product.md'], r'\bD-\d\d\b'),
        ('amendments', files['docs/specs/requirements.md'], r'\b(?:R[2-9]|R10|AM-\d\d)\b'),
    ]:
        errors += id_errors(set(re.findall(pattern, text)), set(ids[label]), label)
    gates = set(re.findall(r'^## Phase integration gate — (PH-\d\d-GATE)$', phase_body, re.M))
    errors += id_errors(gates, {f'PH-{n:02}-GATE' for n in range(23)}, 'gate')
    errors += dependency_errors(manifest['phase_order'], manifest['phase_dependencies'])
    for phase, deps in manifest['phase_dependencies'].items():
        text = files[f'docs/phases/{phase}.md']
        if phase not in {'00', '22'}:
            header = re.search(r'\*\*Prerequisite gates:\*\* (.+)', text)
            actual = set(re.findall(r'\[(\d\d)\]\(\d\d.md#gate\)', header[1] if header else ''))
            errors += id_errors(actual, set(deps), f'phase {phase} prerequisites')
    for name, text in markdown.items():
        if '[cite:' in text:
            errors.append(f'{name}: unresolved citation placeholder')
        if len(re.findall(r'^```', text, re.M)) % 2:
            errors.append(f'{name}: unclosed code fence')
        explicit = re.findall(r'<a id="([^"]+)">', text)
        if len(explicit) != len(set(explicit)):
            errors.append(f'{name}: duplicate explicit anchor')
    for name, max_words in [('AGENTS.md', 750), ('PLAN.md', 1300), ('STATE.md', 950)]:
        words = len(files[name].split())
        if words > max_words:
            errors.append(f'{name}: {words} words exceeds initial {max_words}-word control-file budget')
    if args.baseline:
        for name, expected in manifest['files'].items():
            target = root / name
            if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                errors.append(f'Baseline fingerprint mismatch: {name}')
    if errors:
        for error in errors:
            print('ERROR:', error)
        print(f'FAIL: {len(errors)} documentation errors')
        return 1
    print(f'PASS: {len(markdown)} Markdown files; local links/anchors; 30 requirements; '
          f'17 decisions; 26 amendments; {len(actual_outcomes)} outcomes; {len(actual_acs)} acceptance IDs; '
          '23 phase gates; dependency order; root-file budgets.'
          + (' Static baseline fingerprints match.' if args.baseline else ''))
    print('These are documentation checks, not software, source-availability, or historical-coverage tests.')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
