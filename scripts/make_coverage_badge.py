import json, re, pathlib

xml_path = pathlib.Path('coverage.xml')
if not xml_path.exists():
    print('coverage.xml not found; skipping badge generation')
    raise SystemExit(0)

xml = xml_path.read_text(encoding='utf-8', errors='ignore')
m = re.search(r'lines-rate="([0-9.]+)"', xml)
pct = 0.0 if not m else round(float(m.group(1)) * 100, 1)
color = (
    'brightgreen' if pct >= 90 else
    'green' if pct >= 80 else
    'yellow' if pct >= 65 else
    'orange'
)
badge = {
    "schemaVersion": 1,
    "label": "coverage",
    "message": f"{pct}%",
    "color": color,
}
pathlib.Path('coverage-badge.json').write_text(json.dumps(badge), encoding='utf-8')
print('Wrote coverage-badge.json with', pct)
