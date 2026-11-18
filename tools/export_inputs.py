"""Preserve exact experimental source bytes independently of Git newline settings."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def export_inputs(name='full'):
    manifest_path = ROOT/'runs'/f'benchmark-{name}'/'benchmark.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    destination = ROOT/'reports'/name/'frozen-inputs.zip'
    if destination.exists():
        with zipfile.ZipFile(destination) as archive:
            valid=all(hashlib.sha256(archive.read(path)).hexdigest()==expected
                      for path,expected in manifest['frozen_inputs'].items() if path!='indexes')
        if valid:
            return destination
    sources = []
    for relative, expected in manifest['frozen_inputs'].items():
        if relative == 'indexes':
            continue
        path = (ROOT/relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('Input outside project')
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f'Frozen input changed: {relative}')
        sources.append((relative, content))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, content in sources:
            archive.writestr(relative, content)
        archive.writestr('frozen-inputs.json', json.dumps(manifest['frozen_inputs'], indent=2))
        archive.write(ROOT/'compose.yaml', 'compose.yaml')
        archive.write(ROOT/'data/corpus-manifest.json', 'data/corpus-manifest.json')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='full')
    print(export_inputs(parser.parse_args().name))
