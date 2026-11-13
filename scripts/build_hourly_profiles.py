"""Add filter-aware descriptive measures for local-hour profile comparisons."""
from pathlib import Path
import re
from build_report_presentation import uid

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'fabric/sm_power_renewables.SemanticModel/definition/tables/fact_market_hour.tmdl'


def build():
    price = "'fact_market_hour'[day_ahead_price_eur_mwh]"
    valid = f"FILTER('fact_market_hour', NOT ISBLANK({price}))"
    measures = [
        ('Hourly Median Price', f'MEDIANX({valid}, {price})', '0.00'),
        ('Hourly Price P10', f'PERCENTILEX.INC({valid}, {price}, 0.1)', '0.00'),
        ('Hourly Price P90', f'PERCENTILEX.INC({valid}, {price}, 0.9)', '0.00'),
        ('Average Grid Load GW', "DIVIDE(AVERAGE('fact_market_hour'[grid_load_mwh]), 1000)", '0.00'),
    ]
    groups = """CALCULATETABLE(
        SUMMARIZE('dim_time_hour', 'dim_time_hour'[local_hour], 'dim_time_hour'[is_weekend]),
        REMOVEFILTERS('dim_time_hour'[local_hour]),
        REMOVEFILTERS('dim_time_hour'[is_weekend])
    )"""
    for name, percentile, aggregator, padding in [
        ('Hourly Price Axis Minimum', 'Hourly Price P10', 'MINX', '- 10'),
        ('Hourly Price Axis Maximum', 'Hourly Price P90', 'MAXX', '+ 10'),
    ]:
        bound = f"{'MIN' if aggregator == 'MINX' else 'MAX'}([{percentile}], {'MIN' if aggregator == 'MINX' else 'MAX'}([Average Price EUR per MWh], [Hourly Median Price]))"
        expression = f'''VAR Groups = {groups}
VAR Bounds = ADDCOLUMNS(Groups, "ProfileBound", CALCULATE({bound}))
RETURN {aggregator}(Bounds, [ProfileBound]) {padding}'''
        # The outer evaluation removes the panel filter; each group then reapplies its day type.
        expression = "CALCULATE(\n" + expression + ",\n    REMOVEFILTERS('dim_time_hour'[is_weekend]),\n    REMOVEFILTERS('dim_time_hour'[local_hour])\n)"
        measures.append((name, expression, '0.00'))
    measures.append(('Hourly Power Axis Maximum', f'''CALCULATE(
    VAR Groups = {groups}
    VAR Bounds = ADDCOLUMNS(Groups, "ProfileBound",
        MAX([Average Grid Load GW],
            [Average Solar GW] + [Average Wind GW] + MAX(0, [Average Residual Load GW])))
    RETURN MAXX(Bounds, [ProfileBound]) + 3,
    REMOVEFILTERS('dim_time_hour'[is_weekend]),
    REMOVEFILTERS('dim_time_hour'[local_hour])
)''', '0.00'))
    measures.append(('Hourly Power Axis Minimum', f'''CALCULATE(
    VAR Groups = {groups}
    VAR Bounds = ADDCOLUMNS(Groups, "ProfileBound", [Average Residual Load GW])
    RETURN MIN(0, MINX(Bounds, [ProfileBound]) - 2),
    REMOVEFILTERS('dim_time_hour'[is_weekend]),
    REMOVEFILTERS('dim_time_hour'[local_hour])
)''', '0.00'))
    text = TABLE.read_text()
    for name, expression, fmt in measures:
        text = re.sub(r"\n\tmeasure '" + re.escape(name) + r"' =.*?(?=\n\t(?:measure|column|partition)\s|\Z)", '', text, flags=re.S)
        block = f"\tmeasure '{name}' =\n" + '\n'.join('\t\t\t' + line for line in expression.splitlines())
        block += f'\n\t\tlineageTag: {uid(name)}\n\t\tdisplayFolder: Hourly profiles\n\t\tformatString: {fmt}\n'
        if 'Axis ' in name:
            block += '\t\tisHidden\n'
        text = text.replace('\n\tcolumn ', '\n' + block + '\n\tcolumn ', 1)
    TABLE.write_text(text)
    print('Added eight hourly-profile measures; existing columns and partitions retained')


if __name__ == '__main__':
    build()
