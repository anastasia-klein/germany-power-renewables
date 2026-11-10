"""Add source-aware generation shares and descriptive supply/demand report measures."""
from pathlib import Path
import re
from build_report_presentation import uid

ROOT=Path(__file__).resolve().parents[1]
TABLES=ROOT/'fabric/sm_power_renewables.SemanticModel/definition/tables'


def build():
    # The report source dimension filters the original source dimension, so both
    # source filters must be removed when computing the reported-generation total.
    for path in [TABLES/'fact_generation_hour.tmdl',ROOT/'model/semantic_measures.dax']:
        text=path.read_text().replace("CALCULATE([Generation TWh], REMOVEFILTERS('dim_generation_source'))", "CALCULATE([Generation TWh], REMOVEFILTERS('dim_generation_source'), REMOVEFILTERS('report_source'))")
        text=re.sub(
            r"(?m)^([ \t]*)REMOVEFILTERS\('dim_generation_source'\),\n(?![ \t]*REMOVEFILTERS\('report_source'\))",
            lambda match: match.group(0)+match.group(1)+"REMOVEFILTERS('report_source'),\n",
            text)
        path.write_text(text)
    items=[]
    for label,column in [('Residual Load','residual_load_mwh'),('Wind','wind_mwh'),('Solar','solar_mwh')]:
        items.append(('Average '+label+' GW',f"DIVIDE(AVERAGE('fact_market_hour'[{column}]), 1000)",'0.00'))
        expression=f'''VAR Observations =
    FILTER(
        'fact_market_hour',
        NOT ISBLANK('fact_market_hour'[{column}])
            && NOT ISBLANK('fact_market_hour'[day_ahead_price_eur_mwh])
    )
VAR MeanX = AVERAGEX(Observations, 'fact_market_hour'[{column}] / 1000)
VAR MeanY = AVERAGEX(Observations, 'fact_market_hour'[day_ahead_price_eur_mwh])
VAR CrossProduct =
    SUMX(Observations, ('fact_market_hour'[{column}] / 1000 - MeanX)
        * ('fact_market_hour'[day_ahead_price_eur_mwh] - MeanY))
VAR SumSquaresX = SUMX(Observations, ('fact_market_hour'[{column}] / 1000 - MeanX) ^ 2)
VAR SumSquaresY = SUMX(Observations, ('fact_market_hour'[day_ahead_price_eur_mwh] - MeanY) ^ 2)
RETURN
    IF(COUNTROWS(Observations) >= 2,
        DIVIDE(CrossProduct, SQRT(SumSquaresX * SumSquaresY)))'''
        items.append(('Price Correlation '+label,expression,'0.000'))
    items += [
        ('Heatmap Price EUR per MWh','[Average Price EUR per MWh]','0.0'),
        ('Heatmap Price Color','''VAR Price = [Heatmap Price EUR per MWh]
RETURN
    SWITCH(TRUE(),
        ISBLANK(Price), BLANK(),
        Price < 0, "#8EC5FF",
        Price < 50, "#E9F2FF",
        Price < 100, "#D2E8EF",
        Price < 150, "#F8D995",
        "#ED8B82")''',None),
    ]
    p=TABLES/'fact_market_hour.tmdl';text=p.read_text()
    for name,expr,fmt in items:
        text=re.sub(r"\n\tmeasure '"+re.escape(name)+r"' =.*?(?=\n\t(?:measure|column|partition)\s|\Z)", '',text,flags=re.S)
        block=f"\tmeasure '{name}' =\n"+'\n'.join('\t\t\t'+line for line in expr.splitlines())+f'\n\t\tlineageTag: {uid(name)}\n\t\tdisplayFolder: Supply and demand\n'
        if fmt:block+=f'\t\tformatString: {fmt}\n'
        text=text.replace('\n\tcolumn ','\n'+block+'\n\tcolumn ',1)
    p.write_text(text)
    print('Added eight descriptive measures; generation shares remove both source filters')

if __name__=='__main__':build()
