from pathlib import Path
import json,os,re,tomllib
r=Path(__file__).resolve().parents[1]
tag=os.environ.get('RELEASE_TAG','')
if not re.fullmatch(r'v\d+\.\d+\.\d+',tag):raise SystemExit('Use a release tag such as v1.0.0.')
version=tag[1:]
versions=[json.loads((r/'desktop/package.json').read_text())['version'],tomllib.loads((r/'pyproject.toml').read_text())['project']['version'],re.search(r"versionName '([^']+)'",(r/'android/app/build.gradle').read_text())[1]]
if any(v!=version for v in versions):raise SystemExit('Update all application versions to match the release tag before publishing.')
print('Release versions match:',tag)
