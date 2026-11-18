"""Build a public, portable hourly snapshot from the validated SMARD source files."""
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/smard'
OUT = ROOT / 'web/data'
SOURCES = ['Biomass', 'Hydropower', 'Wind offshore', 'Wind onshore', 'Photovoltaics', 'Other renewable', 'Nuclear', 'Lignite', 'Hard coal', 'Fossil gas', 'Hydro pumped storage', 'Other conventional']


def read(category):
    path = RAW / f'{category}_202501010000_202601010000_Hour.csv'
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle, delimiter=';')), path


def number(value):
    return None if value in ('-', '', None) else float(value.replace(',', ''))


def build():
    consumption, cp = read('Actual_consumption')
    generation, gp = read('Actual_generation')
    prices, pp = read('Day-ahead_prices')
    assert len(consumption) == len(generation) == len(prices) == 8760
    zone = ZoneInfo('Europe/Berlin')
    first = datetime(2025, 1, 1, tzinfo=zone).astimezone(timezone.utc)
    rows = []
    for i, (c, g, p) in enumerate(zip(consumption, generation, prices)):
        utc = first + timedelta(hours=i)
        local = utc.astimezone(zone)
        for source in (c, g, p):
            assert datetime.strptime(source['Start date'], '%b %d, %Y %I:%M %p') == local.replace(tzinfo=None)
        rows.append([
            utc.isoformat().replace('+00:00', 'Z'), local.date().isoformat(), local.hour,
            local.weekday() >= 5, local.month,
            number(p['Germany/Luxembourg [€/MWh] Calculated resolutions']),
            number(c['grid load [MWh] Calculated resolutions']),
            number(c['Residual load [MWh] Calculated resolutions']),
            [number(g[f'{name} [MWh] Calculated resolutions']) for name in SOURCES],
        ])
    design = json.loads((ROOT / 'model/report_presentation.json').read_text())
    data = dict(version=1, year=2025, timezone='Europe/Berlin',
        provenance='Derived locally from the original validated SMARD CSV exports; analytical parity checked against the Fabric report. Not an export of OneLake Delta tables.',
        columns=['utc', 'date', 'hour', 'weekend', 'month', 'price', 'load', 'residual', 'generation'],
        sources=design['sources'], rows=rows,
        source_files=[dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (cp, gp, pp)])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'market-2025.json').write_text(json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n')
    print(f'Built {len(rows)} physical hours, {len(design["sources"])} sources; {len(json.dumps(data)):,} JSON characters')


if __name__ == '__main__':
    build()
