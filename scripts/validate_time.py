"""Validate the three full-year hourly SMARD exports without changing raw data.

Scope: chronological exports for the complete local calendar year 2025.
Each file is checked independently against a UTC timeline rendered in Europe/Berlin.
Never infer keys from row numbers without this complete sequence check.
"""
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/smard'
OUT = ROOT / 'data/validation'
ZONE = ZoneInfo('Europe/Berlin')
FORMAT = '%b %d, %Y %I:%M %p'


def main():
    begin = datetime(2025, 1, 1, tzinfo=ZONE).astimezone(timezone.utc)
    finish = datetime(2026, 1, 1, tzinfo=ZONE).astimezone(timezone.utc)
    instants = []
    cursor = begin
    while cursor < finish:
        instants.append(cursor)
        cursor += timedelta(hours=1)
    expected = [t.astimezone(ZONE).replace(tzinfo=None) for t in instants]
    reports = []
    for name in ('Actual_consumption', 'Actual_generation', 'Day-ahead_prices'):
        path = RAW / f'{name}_202501010000_202601010000_Hour.csv'
        with path.open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle, delimiter=';'))
        observed = [datetime.strptime(r['Start date'], FORMAT) for r in rows]
        if observed != expected:
            raise ValueError(f'{path.name}: unexpected order, coverage or time labels')
        # Export end labels are wall-clock labels, not reliable physical boundaries
        # at DST transitions. Require the observed SMARD display convention.
        if any(datetime.strptime(r['End date'], FORMAT) != s + timedelta(hours=1)
               for r, s in zip(rows, observed)):
            raise ValueError(f'{path.name}: unexpected end-label convention')
        reports.append({'file': path.name, 'rows': len(rows),
                        'utc_keys_unique': len(set(instants)) == len(rows),
                        'all_start_labels_match_expected_timeline': True,
                        'missing_or_extra_intervals': 0})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'dim_time_hour_2025.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['time_key', 'interval_start_utc', 'interval_end_utc',
                         'local_date', 'local_hour', 'utc_offset_minutes', 'fold',
                         'duration_minutes'])
        for t in instants:
            local = t.astimezone(ZONE)
            writer.writerow([t.strftime('%Y%m%d%H'), t.isoformat(),
                             (t + timedelta(hours=1)).isoformat(),
                             local.date().isoformat(), local.hour,
                             int(local.utcoffset().total_seconds() / 60),
                             local.fold, 60])
    counts = Counter(t.date().isoformat() for t in expected)
    report = {
        'scope': 'Complete chronological hourly SMARD exports for local year 2025',
        'timezone_source': 'https://www.smard.de/en/change-from-summer-to-winter-time-218202',
        'files': reports,
        'utc_start_inclusive': begin.isoformat(),
        'utc_end_exclusive': finish.isoformat(),
        'local_days_with_non_24_hours': {k: v for k, v in counts.items() if v != 24},
        'naive_three_way_join_rows': sum(n ** 3 for n in Counter(expected).values()),
        'utc_three_way_join_rows': len(instants),
        'end_time_policy': 'Derive physical end as UTC start plus 60 minutes; retain original end label in staging',
        'limitations': 'For partial, shuffled or incomplete exports, stop; do not assign keys by row position.'
    }
    (OUT / 'time_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
