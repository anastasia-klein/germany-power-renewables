"""Build the native Fabric PBIR report bound to the existing Direct Lake model.

Design reference: the author's Global Critical Materials report. The reference
project is not modified. Report queries use persisted model measures only.
"""
from pathlib import Path
import json
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'fabric/rpt_power_renewables.Report'
BASE = 'https://developer.microsoft.com/json-schemas/fabric/'
DESIGN = json.loads((ROOT / 'model/report_presentation.json').read_text())
C = DESIGN['colors']
FONT = DESIGN['font']
R = 'report_source'
MONTH = 'report_month'
AXIS = 'report_axis'
PAGES = [('01_market', 'Market overview'), ('02_generation', 'Generation & value'), ('03_negative', 'Negative prices'), ('04_supply', 'Supply & demand')]
M = 'fact_market_hour'
G = 'fact_generation_hour'
T = 'dim_time_hour'
S = 'dim_generation_source'


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def ident(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'germany-power-renewables/report/' + name))


def lit(value):
    if isinstance(value, bool):
        value = 'true' if value else 'false'
    elif isinstance(value, str):
        value = "'" + value.replace("'", "''") + "'"
    else:
        value = str(value) + 'D'
    return {'expr': {'Literal': {'Value': value}}}


def color(value):
    return {'solid': {'color': lit(value)}}


def props(**kwargs):
    return [{'properties': kwargs}]


def field(table, name, measure=False):
    return {('Measure' if measure else 'Column'): {'Expression': {'SourceRef': {'Entity': table}}, 'Property': name}}


def projection(table, name, measure=False):
    return {'field': field(table, name, measure), 'queryRef': table + '.' + name,
            'nativeQueryRef': name, 'displayName': {'Timeline Average Price':'Market average','Timeline Load Weighted Price':'Load-weighted','Timeline Capture Price':'Source capture','Timeline Capture Rate':'Capture rate','Timeline Negative Price Hours':'Negative hours','Timeline Negative Price Share':'Negative-hour share','Timeline Wind Solar Load Ratio':'Wind + solar / load'}.get(name,name), 'active': True}


def measure(name, table=M):
    return (table, name, True)


class Page:
    def __init__(self, name, title, question, subtitle, footnote):
        self.name, self.title, self.visuals, self.overrides = name, title, [], []
        self.text(28, 14, 590, 62, 'Germany Power & Renewables', 25, True)
        self.text(29, 72, 570, 25, 'POWER MARKET RESEARCH  ·  SMARD  ·  2025', 10)
        for index,(page_name,_) in enumerate(PAGES):
            panel=self.add('shape',650+index*(922/len(PAGES)),24,922/len(PAGES)-8,48,objects={'shape':props(tileShape=lit('rectangle')),'fill':props(show=lit(False)),'outline':props(show=lit(False))})
            panel['visual']['visualContainerObjects']['background']=props(show=lit(True),color=color('#E2EEFF' if page_name==name else C['panel']),transparency=lit(0))
            panel['visual']['visualContainerObjects']['border']=props(show=lit(True),color=color('#D8E7FA' if page_name==name else C['edge']),radius=lit(8),width=lit(1))
            panel['visual']['visualContainerObjects']['dropShadow']=props(show=lit(False))
        self.add('pageNavigator', 650, 24, 922, 48, transparent=True, objects={
            'layout': props(orientation=lit(2), cellPadding=lit(8)),
            'text': [{'selector': {'id': state}, 'properties': {
                'fontFamily': lit(FONT), 'fontSize': lit(11), 'bold': lit(state == 'selected'),
                'fontColor': color('#2463A9' if state == 'selected' else C['muted'])}}
                     for state in ['default', 'selected']],
            'fill': [{'selector': {'id': state}, 'properties': {
                'show': lit(False), 'fillColor': color('#FFFFFF'), 'transparency': lit(100)}}
                     for state in ['default', 'selected']],
            'outline': props(show=lit(False)), 'shape': props(tileShape=lit('rectangleRoundedByPixel'), rectangleRoundedCurve=lit(8))})
        self.text(28, 97, 800, 48, question, 26, True)
        self.text(29, 146, 800, 36, subtitle, 10)
        self.slicer(1220, 96, 352, 'Month · 2025', MONTH, 'month_name')
        self.text(28, 856, 1050, 38, footnote, 9)
        self.text(1100, 854, 472, 22, 'Bundesnetzagentur | SMARD.de · CC BY 4.0', 9, align='right')


    def add(self, kind, x, y, w, h, title='', roles=None, objects=None, transparent=False):
        name = ident(self.name + '/' + str(len(self.visuals)) + '/' + kind).replace('-', '')[:20]
        container = {
            'background': props(show=lit(not transparent), color=color(C['panel']), transparency=lit(100 if transparent else 0)),
            'border': props(show=lit(not transparent), color=color(C['edge']), radius=lit(18), width=lit(1)),
            'dropShadow': props(show=lit(not transparent), color=color('#435B53'), position=lit('Outer'), preset=lit('Custom'), shadowBlur=lit(10), shadowDistance=lit(2), shadowSpread=lit(0), angle=lit(90), transparency=lit(94)),
            'visualHeader': props(show=lit(False)),
            'title': props(show=lit(bool(title)), text=lit(title), fontColor=color(C['text']), fontFamily=lit(FONT), fontSize=lit(12), bold=lit(True)),
            'padding': props(top=lit(0 if transparent else 10), bottom=lit(0 if transparent else 8), left=lit(0 if transparent else 12), right=lit(0 if transparent else 12)),
            'general': props(altText=lit(title or kind), keepLayerOrder=lit(True))}
        visual = {'visualType': kind, 'visualContainerObjects': container, 'drillFilterOtherVisuals': True}
        if roles:
            visual['query'] = {'queryState': {role: {'projections': [projection(*item) for item in items]} for role, items in roles.items()}}
        if objects:
            visual['objects'] = objects
        out = {'$schema': BASE + 'item/report/definition/visualContainer/2.5.0/schema.json', 'name': name,
               'position': dict(x=x, y=y, width=w, height=h, z=len(self.visuals)*1000, tabOrder=len(self.visuals)*1000), 'visual': visual}
        self.visuals.append(out)
        return out

    def text(self, x, y, w, h, text, size=11, bold=False, align='left'):
        return self.add('textbox', x, y, w, h, transparent=True, objects={'general': props(paragraphs=[{
            'textRuns': [{'value': text, 'textStyle': {'fontFamily': FONT, 'fontSize': str(size)+'pt', 'fontWeight': 'bold' if bold else 'normal', 'color': C['text'] if bold else C['muted']}}],
            'horizontalTextAlignment': align}])})

    def slicer(self, x, y, w, title, table, column, default=None):
        objects = {'data': props(mode=lit('Dropdown')), 'header': props(show=lit(False)),
                   'items': props(fontColor=color(C['text']), background=color(C['panel']), fontFamily=lit(FONT), textSize=lit(11)),
                   'general': props(outlineWeight=lit(0), outlineColor=color(C['panel'])),
                   'selection': props(singleSelect=lit(default is not None), strictSingleSelect=lit(default is not None), selectAllCheckboxEnabled=lit(default is None))}
        if default is not None:
            objects['general'] = props(outlineWeight=lit(0), outlineColor=color(C['panel']), filter={'filter': {'Version': 2, 'From': [{'Name': 's', 'Entity': table, 'Type': 0}], 'Where': [{'Condition': {'In': {
                'Expressions': [{'Column': {'Expression': {'SourceRef': {'Source': 's'}}, 'Property': column}}],
                'Values': [[{'Literal': {'Value': "'"+default+"'"}}]]}}}]}})
        self.text(x+2,y,w-4,24,title,10,True)
        visual = self.add('slicer', x, y+26, w, 40, '', {'Values': [(table, column, False)]}, objects)
        visual['visual']['visualContainerObjects']['border']=props(show=lit(True),color=color(C['edge']),radius=lit(7),width=lit(1))
        visual['visual']['visualContainerObjects']['dropShadow']=props(show=lit(False))
        visual['visual']['visualContainerObjects']['padding']=props(top=lit(3),bottom=lit(3),left=lit(8),right=lit(8))
        visual['filterConfig'] = {'filters': [{'name': 'available_values', 'field': field(table, column), 'type': 'Categorical', 'filter': {
            'Version': 2, 'From': [{'Name': 's', 'Entity': table, 'Type': 0}], 'Where': [{'Condition': {'Not': {'Expression': {'In': {
                'Expressions': [{'Column': {'Expression': {'SourceRef': {'Source': 's'}}, 'Property': column}}],
                'Values': [[{'Literal': {'Value': 'null'}}]]}}}}}]}, 'howCreated': 'User', 'isHiddenInViewMode': True}]}
        return visual

    def card(self, x, title, name, table=M, accent='blue'):
        return self.add('card', x, 188, 370, 96, title, {'Values': [measure(name, table)]}, {
            'labels': props(color=color(C[accent]), fontFamily=lit(FONT), fontSize=lit(28), labelDisplayUnits=lit(1)),
            'categoryLabels': props(show=lit(False))})

    def chart(self, kind, x, y, w, h, title, axis, metrics, colors=None, descending=False):
        objects = {
            'categoryAxis': props(labelColor=color(C['muted']), fontFamily=lit(FONT), fontSize=lit(10), showAxisTitle=lit(False)),
            'valueAxis': props(labelColor=color(C['muted']), fontFamily=lit(FONT), fontSize=lit(10), showAxisTitle=lit(False), gridlineColor=color(C['edge']), gridlineShow=lit(True)),
            'legend': props(show=lit(len(metrics)>1), showTitle=lit(False), labelColor=color(C['text']), fontFamily=lit(FONT), fontSize=lit(10), position=lit('Top')),
            'labels': props(color=color(C['text']), fontFamily=lit(FONT), fontSize=lit(10))}
        if kind == 'lineChart':
            objects['categoryAxis'][0]['properties']['axisType'] = lit('Categorical')
            objects['lineStyles'] = props(showMarker=lit(True), showMarkerByDefault=lit(True), markerSize=lit(4), strokeWidth=lit(2.5), lineChartType=lit('linear'))
        if colors:
            objects['dataPoint'] = props(fill=color(colors[0])) if len(metrics) == 1 and kind != 'lineChart' else [{'selector': {'metadata': m[0]+'.'+m[1]}, 'properties': {'fill': color(c)}} for m,c in zip(metrics,colors)]
        visual = self.add(kind,x,y,w,h,title,{'Category':[axis], 'Y':metrics},objects)
        sort_field = metrics[0] if descending else (AXIS, 'axis_order', False) if axis[0] == AXIS else axis
        visual['visual']['query']['sortDefinition'] = {'sort':[{'field':field(*sort_field),'direction':'Descending' if descending else 'Ascending'}], 'isDefaultSort':True}
        return visual

    def scatter(self,x,w,title,x_measure,accent):
        visual=self.add('scatterChart',x,302,w,190,title,{
            'Category':[(T,'time_key',False)],'X':[measure(x_measure)],
            'Y':[measure('Average Price EUR per MWh')],
            'Tooltips':[(T,'interval_start_utc',False),(T,'local_hour',False)]},{
            'general':props(dataVolume=lit(10000)),
            'categoryAxis':props(labelColor=color(C['muted']),fontFamily=lit(FONT),fontSize=lit(9),showAxisTitle=lit(True),titleText=lit(title.split(' vs.')[0]+' · GW')),
            'valueAxis':props(labelColor=color(C['muted']),fontFamily=lit(FONT),fontSize=lit(9),labelDisplayUnits=lit(1),labelPrecision=lit(0),start=lit(-260),end=lit(600),showAxisTitle=lit(True),titleText=lit('EUR/MWh'),gridlineColor=color(C['edge']),gridlineShow=lit(True)),
            'legend':props(show=lit(False)),'categoryLabels':props(show=lit(False)),
            'fillPoint':props(style=lit('Fill only')), 'markers':props(transparency=lit(65)), 'dataPoint':props(fill=color(C[accent])),
            'bubbles':props(bubbleSize=lit(1),preventOverflow=lit(True))})
        return visual

    def finish(self):
        for item in self.visuals:
            visual=item['visual'];roles=visual.get('query',{}).get('queryState',{});kind=visual['visualType']
            if self.name == '02_generation':
                if kind == 'card':
                    visual['objects']['labels'][0]['properties']['color']={'solid':{'color':{'expr':field(G,'Generation Source Color',True)}}}
                for projection_item in roles.get('Y',{}).get('projections',[]):
                    measure_name=projection_item['field'].get('Measure',{}).get('Property','')
                    if measure_name in ['Timeline Capture Price','Timeline Capture Rate']:
                        dynamic={'solid':{'color':{'expr':field(G,'Generation Source Color',True)}}}
                        if kind == 'lineChart':
                            for entry in visual['objects']['dataPoint']:
                                if entry.get('selector',{}).get('metadata') == G+'.'+measure_name:entry['properties']['fill']=dynamic
                        else:
                            visual['objects']['dataPoint']=[{'selector':{'data':[{'dataViewWildcard':{'matchingOption':1}}]},'properties':{'fill':dynamic}}]
            if self.name == '03_negative' and kind == 'clusteredBarChart':
                visual['objects']['dataPoint']=[{'selector':{'data':[{'dataViewWildcard':{'matchingOption':1}}]},'properties':{'fill':{'solid':{'color':{'expr':field(G,'Generation Source Color',True)}}}}}]
        # Slicers filter the page. Charts do not change the meaning of other KPIs.
        charts=[v for v in self.visuals if v['visual']['visualType'] in ['lineChart','clusteredBarChart','clusteredColumnChart','tableEx','scatterChart','pivotTable']]
        targets=[v for v in self.visuals if v['visual']['visualType'] != 'textbox']
        interactions=[{'source':a['name'],'target':b['name'],'type':'NoFilter'} for a in charts for b in targets if a!=b]
        interactions += self.overrides
        folder=REPORT/'definition/pages'/self.name
        save(folder/'page.json',{'$schema':BASE+'item/report/definition/page/2.0.0/schema.json','name':self.name,'displayName':self.title,'displayOption':'FitToPage','width':1600,'height':900,
            'objects':{'background':props(color=color(C['canvas']),transparency=lit(0)),'outspace':props(color=color(C['canvas']),transparency=lit(0))},'visualInteractions':interactions})
        current_names={visual['name'] for visual in self.visuals}
        for stale in (folder/'visuals').glob('*/visual.json'):
            if stale.parent.name not in current_names:
                stale.unlink()
                if not any(stale.parent.iterdir()):stale.parent.rmdir()
        for visual in self.visuals:
            save(folder/'visuals'/visual['name']/'visual.json',visual)


def build():
    theme={'name':'Germany Power · Mineral','dataColors':[C['blue'],C['amber'],C['teal'],C['slate'],C['green'],C['red']],
           'background':C['canvas'],'foreground':C['text'],'tableAccent':C['teal'],'good':C['teal'],'neutral':C['amber'],'bad':C['red'],
           'textClasses':{k:{'fontFace':FONT,'fontSize':size,'color':C['muted'] if k=='label' else C['text']} for k,size in [('callout',28),('title',14),('header',12),('label',10)]}}
    save(REPORT/'StaticResources/RegisteredResources/GermanyPowerMineral.json',theme)
    save(REPORT/'.platform',{'$schema':BASE+'gitIntegration/platformProperties/2.0.0/schema.json','metadata':{'type':'Report','displayName':'Germany Power & Renewables','description':'Hourly 2025 market overview, generation value and negative-price exposure; connected to sm_power_renewables.'},'config':{'version':'2.0','logicalId':ident('rpt_power_renewables')}})
    save(REPORT/'definition.pbir',{'$schema':BASE+'item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../sm_power_renewables.SemanticModel'}}})
    save(REPORT/'definition/version.json',{'$schema':BASE+'item/report/definition/versionMetadata/1.0.0/schema.json','version':'2.0.0'})
    save(REPORT/'definition/report.json',{'$schema':BASE+'item/report/definition/report/3.0.0/schema.json',
        'themeCollection':{'customTheme':{'name':'GermanyPowerMineral','reportVersionAtImport':{'visual':'2.5.0','page':'2.0.0','report':'3.0.0'},'type':'RegisteredResources'}},
        'resourcePackages':[{'name':'RegisteredResources','type':'RegisteredResources','items':[{'name':'GermanyPowerMineral','path':'GermanyPowerMineral.json','type':'CustomTheme'}]}],
        'objects':{'outspacePane':props(expanded=lit(False))},'settings':{'useStylableVisualContainerHeader':True,'exportDataMode':'AllowSummarized','useEnhancedTooltips':False}})
    save(REPORT/'definition/pages/pages.json',{'$schema':BASE+'item/report/definition/pagesMetadata/1.0.0/schema.json','pageOrder':[p[0] for p in PAGES],'activePageName':PAGES[0][0]})
    month=(AXIS,'axis_label',False)
    p=Page(*PAGES[0],'How did the German power market move?', 'Germany load & generation · DE/LU day-ahead price · Select one month for daily detail',
           'Hourly export · Local calendar: Europe/Berlin · UTC preserves repeated DST hours · Descriptive analysis')
    for x,label,name,accent in [(28,'Market average · EUR/MWh','Average Price EUR per MWh','blue'),(420,'Load-weighted · EUR/MWh','Load Weighted Price EUR per MWh','teal'),(812,'Grid load · TWh','Grid Load TWh','slate')]:p.card(x,label,name,accent=accent)
    p.card(1204,'Renewables / reported generation','Renewable Share of Reported Generation',G,'green')
    p.chart('lineChart',28,302,920,300,'Price profile · time average vs load-weighted · EUR/MWh',month,[measure('Timeline Average Price'),measure('Timeline Load Weighted Price')],[C['blue'],C['teal']])
    p.chart('lineChart',28,620,920,220,'Wind + solar / grid load · ratio of energy sums',month,[measure('Timeline Wind Solar Load Ratio')],[C['amber']])
    mix=p.chart('clusteredBarChart',968,302,606,538,'Generation mix · share of reported output',(R,'source_label',False),[measure('Generation Share',G)],[C['slate']],descending=True)
    mix['visual']['objects']['categoryAxis'][0]['properties'].update(maxMarginFactor=lit(60),fontSize=lit(9.5))
    mix['visual']['objects']['labels']=props(show=lit(True),color=color(C['text']),fontFamily=lit(FONT),fontSize=lit(9.5),labelPrecision=lit(1),labelDisplayUnits=lit(1),labelPosition=lit('OutsideEnd'),labelOverflow=lit(True))
    mix['visual']['query']['queryState']['Tooltips']={'projections':[projection(G,'Generation TWh',True)]}
    # Stable category colors identify technologies, rather than changing with sorting.
    source_colors={source['label']:source['color'] for source in DESIGN['sources']}
    mix['visual']['objects']['dataPoint']=[{'selector':{'data':[{'scopeId':{'Comparison':{'ComparisonKind':0,'Left':field(R,'source_label'),'Right':{'Literal':{'Value':"'"+label+"'"}}}}}]},'properties':{'fill':color(c)}} for label,c in source_colors.items()]
    p.finish()
    p=Page(*PAGES[1],'When does generation capture market value?', 'Source-weighted prices describe timing exposure · They do not measure generator revenue or profit',
           'Pumped storage is storage output · Nuclear unavailable · Capture requires complete source coverage')
    selector=p.slicer(850,96,352,'Selected generation source',R,'source_label','Solar (Photovoltaics)')
    for x,label,name,accent in [(28,'Selected generation · TWh','Generation TWh','amber'),(420,'Capture price · EUR/MWh','Capture Price EUR per MWh','amber'),(812,'Capture / market average','Capture Rate','teal'),(1204,'MWh in negative-price hours','Negative Price Generation Share','red')]:p.card(x,label,name,G,accent)
    p.chart('lineChart',28,302,1028,310,'Selected source capture price vs market average · EUR/MWh',month,[measure('Timeline Average Price'),measure('Timeline Capture Price',G)],[C['blue'],C['amber']])
    p.chart('clusteredColumnChart',28,630,1028,210,'Selected source · capture rate',month,[measure('Timeline Capture Rate',G)],[C['amber']])
    table=p.add('tableEx',1074,302,500,538,'All sources · comparison for the selected months',{'Values':[measure('Generation Source Icon',G),(R,'source_label',False),measure('Generation TWh',G),measure('Capture Price EUR per MWh',G),measure('Capture Rate',G)]},{
        'values':props(fontColor=color(C['text']),backColorPrimary=color(C['panel']),backColorSecondary=color('#F5F7F5'),fontFamily=lit(FONT),fontSize=lit(9.5),wordWrap=lit(True)),
        'columnHeaders':props(fontColor=color(C['text']),backColor=color(C['panel']),fontFamily=lit(FONT),fontSize=lit(9.5),bold=lit(True),wordWrap=lit(True)),
        'grid':props(gridHorizontal=lit(True),gridHorizontalColor=color(C['edge']),gridVertical=lit(False),rowPadding=lit(5),imageHeight=lit(22),imageWidth=lit(24)), 'total':props(totals=lit(False))})
    for item,label in zip(table['visual']['query']['queryState']['Values']['projections'],['Icon','Source','TWh','Capture EUR/MWh','Capture rate']):item['displayName']=label
    p.overrides.append({'source':selector['name'],'target':table['name'],'type':'NoFilter'})
    p.finish()
    p=Page(*PAGES[2],'When did power prices turn negative?', 'Frequency of negative hourly prices · Compare calendar patterns and generation exposure',
           'Negative hourly averages, not negative quarter-hours · High solar output does not always imply negative prices')
    for x,label,name,table,accent in [(28,'Negative-price hours','Negative Price Hours',M,'red'),(420,'Share of valid hours','Negative Price Hour Share',M,'red'),(812,'Wind + solar / grid load','Wind Solar Load Ratio',M,'teal'),(1204,'Valid physical hours','Valid Price Hours',M,'slate')]:p.card(x,label,name,table,accent)
    p.chart('clusteredColumnChart',28,302,764,304,'Negative-price hours · selected period',month,[measure('Timeline Negative Price Hours')],[C['red']])
    p.chart('clusteredColumnChart',810,302,764,304,'Negative-price frequency by local hour · share of observed hours',(T,'local_hour',False),[measure('Negative Price Hour Share')],[C['red']])
    p.chart('lineChart',28,624,764,216,'Negative-price frequency · share of observed hours',month,[measure('Timeline Negative Price Share')],[C['red']])
    exposure = p.chart('clusteredBarChart',810,624,764,216,'Wind & solar exposure · share of source MWh in negative hours',(R,'source_label',False),[measure('Negative Price Generation Share',G)],[C['amber']],descending=True)
    exposure['filterConfig'] = {'filters': [{'name': 'variable_renewables', 'field': field(S,'generation_source_code'), 'type':'Categorical', 'filter': {
        'Version':2, 'From':[{'Name':'s','Entity':S,'Type':0}], 'Where':[{'Condition':{'In':{
            'Expressions':[{'Column':{'Expression':{'SourceRef':{'Source':'s'}},'Property':'generation_source_code'}}],
            'Values':[[{'Literal':{'Value':"'"+code+"'"}}] for code in ['solar','wind_onshore','wind_offshore']]}}}]}, 'howCreated':'User', 'isHiddenInViewMode':True}]}

    p.finish()
    p=Page(*PAGES[3],'What aligns with the hourly price?',
           'Each point is one physical hour · Raw Pearson correlations · Month filter applies',
           'Hourly associations, not causal effects · Scatter may sample overlapping points · Heatmap: mean price in each month × local-hour cell')
    for x,label,name,accent in [(28,'Price / residual load · Pearson r','Price Correlation Residual Load','blue'),(420,'Price / wind · Pearson r','Price Correlation Wind','teal'),(812,'Price / solar · Pearson r','Price Correlation Solar','amber'),(1204,'Matched physical hours','Valid Price Hours','slate')]:p.card(x,label,name,M,accent)
    p.scatter(28,502,'Residual load vs. price','Average Residual Load GW','blue')
    p.scatter(548,502,'Wind vs. price','Average Wind GW','teal')
    p.scatter(1068,506,'Solar (Photovoltaics) vs. price','Average Solar GW','amber')
    heatmap=p.add('pivotTable',28,510,1546,330,'Average day-ahead price · month × local hour · EUR/MWh',{
        'Rows':[(MONTH,'month_short',False)],'Columns':[(T,'local_hour',False)],
        'Values':[measure('Heatmap Price EUR per MWh')]},{
        'values':props(fontColor=color(C['text']),fontFamily=lit(FONT),fontSize=lit(8.5),wordWrap=lit(False)),
        'rowHeaders':props(fontColor=color(C['text']),fontFamily=lit(FONT),fontSize=lit(9),wordWrap=lit(False),stepped=lit(False)),
        'columnHeaders':props(fontColor=color(C['muted']),fontFamily=lit(FONT),fontSize=lit(8.5),wordWrap=lit(False),autoSizeColumnWidth=lit(False),defaultColumnWidth=lit(58),customColumnWidth=lit(True),alignment=lit('center')),
        'grid':props(gridHorizontal=lit(False),gridVertical=lit(False),rowPadding=lit(2)),
        'subTotals':props(rowSubtotals=lit(False),columnSubtotals=lit(False)),
        'columnFormatting':[{'selector':{'metadata':M+'.Heatmap Price EUR per MWh','data':[{'dataViewWildcard':{'matchingOption':1}}]},'properties':{
            'backColor':{'solid':{'color':{'expr':field(M,'Heatmap Price Color',True)}}},
            'fontColor':color(C['text']),'alignment':lit('center'),
            'styleValues':lit(True),'styleSubtotals':lit(False)}}]})
    heatmap['visual']['objects']['values'].append({'selector':{'metadata':M+'.Heatmap Price EUR per MWh','data':[{'dataViewWildcard':{'matchingOption':1}}]},'properties':{'backColor':{'solid':{'color':{'expr':field(M,'Heatmap Price Color',True)}}}}})
    heatmap['visual']['query']['queryState']['Rows']['projections'][0]['displayName']='Month'
    heatmap['visual']['query']['queryState']['Columns']['projections'][0]['displayName']='Hour'
    heatmap['visual']['query']['sortDefinition']={'sort':[{'field':field(MONTH,'month_number'),'direction':'Ascending'},{'field':field(T,'local_hour'),'direction':'Ascending'}],'isDefaultSort':True}
    p.text(894,518,664,24,'Blue <0 · Pale blue 0–50 · Teal 50–100 · Amber 100–150 · Coral ≥150',8,align='right')
    p.finish()
    print('Built four-page native PBIR report connected to sm_power_renewables')


if __name__ == '__main__':
    build()
