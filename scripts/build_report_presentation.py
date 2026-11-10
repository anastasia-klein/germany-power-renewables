"""Version presentation metadata and adaptive time-axis measures for the 2025 report.

The three small Import calculated tables contain only fixed calendar labels and
source styling. The five existing gold tables retain their Direct Lake partitions.
"""
from pathlib import Path
from datetime import date, timedelta
import calendar
import json
import re
import uuid
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'fabric/sm_power_renewables.SemanticModel/definition'
COLORS={'canvas':'#F5F8FC','panel':'#FFFFFF','edge':'#E0E8F3','text':'#203349','muted':'#65768A',
        'blue':'#397FE5','teal':'#12A89D','amber':'#F1B63D','red':'#EA6C73','green':'#65B87C','slate':'#8298B0'}
SOURCES=[
 ('biomass','Biomass','#65B87C','leaf'),('hydropower','Hydropower','#4A9DE3','water'),
 ('wind_offshore','Wind offshore','#56BED7','offshore'),('wind_onshore','Wind onshore','#12A89D','wind'),
 ('solar','Solar (photovoltaics)','#F1B63D','sun'),('other_renewable','Other renewable','#A0CD8C','sprout'),
 ('nuclear','Nuclear','#9C91C7','atom'),('lignite','Lignite','#B29378','coal'),
 ('hard_coal','Hard coal','#71859B','coal'),('fossil_gas','Fossil gas','#F39A70','flame'),
 ('pumped_storage','Pumped storage','#9D8DE5','storage'),('other_conventional','Other conventional','#A9B8CA','plant')]
ICONS={
 'sun':'<circle cx="16" cy="16" r="5"/><path d="M16 2v4m0 20v4M2 16h4m20 0h4M6 6l3 3m14 14 3 3M6 26l3-3M23 9l3-3"/>',
 'wind':'<path d="M3 12h18c7 0 7-9 1-9-3 0-4 2-4 4M3 17h23c5 0 5 8 0 8-2 0-3-1-3-3M3 22h10c5 0 5 7 0 7"/>',
 'offshore':'<path d="M16 9v16m0-16L8 3m8 6 10-3m-10 3-3 10M3 27q4-4 8 0t8 0 10 0"/><circle cx="16" cy="9" r="2"/>',
 'water':'<path d="M16 2C13 9 6 15 6 21a10 10 0 0 0 20 0c0-6-7-12-10-19Z"/><path d="M11 21c0 4 3 5 5 5"/>',
 'leaf':'<path d="M27 4C10 1 2 10 7 22 19 29 28 20 27 4ZM4 29 23 9m-9 10v-8m0 8h8"/>',
 'sprout':'<path d="M16 29V15M16 20C3 21 3 9 3 9c10-2 14 3 13 11Zm0-7C16 2 29 3 29 3s1 12-13 10Z"/>',
 'atom':'<ellipse cx="16" cy="16" rx="14" ry="5"/><ellipse cx="16" cy="16" rx="14" ry="5" transform="rotate(60 16 16)"/><ellipse cx="16" cy="16" rx="14" ry="5" transform="rotate(120 16 16)"/><circle cx="16" cy="16" r="1"/>',
 'coal':'<path d="m4 23 3-12 8-6 12 8 1 13H8Zm3-12 9 5 11-3m-11 3-2 10"/>',
 'flame':'<path d="M17 2c3 10-5 10-3 16 4-1 7-6 7-6 10 11 4 18-5 18S1 20 8 13c0 7 4 7 4 7C7 12 14 8 17 2Z"/>',
 'storage':'<path d="M4 24h24M7 7h18v12H7ZM12 3h8m-4 8v5m-3-2 3 3 3-3M5 29h22"/>',
 'plant':'<path d="M3 29V15l8 4v-8l8 7V8h6l2 21ZM8 24h2m5 0h2m5 0h2M20 3h4"/>'}


def uid(value):return str(uuid.uuid5(uuid.NAMESPACE_URL,'gpr/presentation/'+value))
def dax_string(value):return '"'+str(value).replace('"','""')+'"'
def svg_uri(kind,fg):
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><g fill="none" stroke="{fg}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[kind]}</g></svg>'
 return 'data:image/svg+xml;utf8,'+quote(svg,safe='')


def table(name,columns,rows):
 out=f'/// Static presentation metadata for the 2025 research report.\ntable {name}\n\tlineageTag: {uid(name)}\n'
 for col,datatype,sort,category in columns:
  out+=f'\n\tcolumn {col}\n\t\tdataType: {datatype}\n\t\tlineageTag: {uid(name+col)}\n\t\tsummarizeBy: none\n\t\tsourceColumn: [{col}]\n'
  if sort:out+=f'\t\tsortByColumn: {sort}\n'
  if category:out+=f'\t\tdataCategory: {category}\n'
 out+=f'\n\tpartition {name} = calculated\n\t\tmode: import\n\t\tsource =\n\t\t\tDATATABLE(\n'
 out+='\t\t\t\t'+', '.join(dax_string(c[0])+', '+('INTEGER' if c[1]=='int64' else 'STRING') for c in columns)+',\n\t\t\t\t{\n'
 out+=',\n'.join('\t\t\t\t\t{'+', '.join(str(v) if isinstance(v,int) else dax_string(v) for v in row)+'}' for row in rows)
 out+='\n\t\t\t\t}\n\t\t\t)\n'
 (MODEL/'tables'/f'{name}.tmdl').write_text(out)


def build():
 months=[(m,calendar.month_name[m],calendar.month_abbr[m]) for m in range(1,13)]
 table('report_month',[('month_number','int64',None,None),('month_name','string','month_number',None),('month_short','string','month_number',None)],months)
 axis=[('Month',calendar.month_abbr[m],m*100,m,0) for m in range(1,13)]
 current=date(2025,1,1)
 while current.year==2025:
  axis.append(('Day',current.strftime('%d %b'),current.month*100+current.day,current.month,current.day));current+=timedelta(days=1)
 table('report_axis',[('grain','string',None,None),('axis_label','string','axis_order',None),('axis_order','int64',None,None),('month_number','int64',None,None),('day_number','int64',None,None)],axis)
 styles=[(code,label,fg,svg_uri(kind,fg)) for code,label,fg,kind in SOURCES]
 table('report_source',[('source_code','string',None,None),('source_label','string',None,None),('source_color','string',None,None),('source_icon','string',None,'ImageUrl')],styles)
 for name,key,target,targetkey in [('report_month','month_number','dim_time_hour','month'),('report_source','source_code','dim_generation_source','generation_source_code')]:
  p=MODEL/'relationships.tmdl';text=p.read_text();relationship=f'relationship {uid(name+"relationship")}\n\tfromColumn: {target}.{targetkey}\n\ttoColumn: {name}.{key}\n'
  if uid(name+'relationship') not in text:p.write_text(text.rstrip()+'\n\n'+relationship)
 p=MODEL/'model.tmdl';text=p.read_text()
 for name in ['report_month','report_axis','report_source']:
  if 'ref table '+name not in text:text+='ref table '+name+'\n'
 p.write_text(text)
 wrappers=[('fact_market_hour','Timeline Average Price','Average Price EUR per MWh','0.00'),('fact_market_hour','Timeline Load Weighted Price','Load Weighted Price EUR per MWh','0.00'),('fact_market_hour','Timeline Wind Solar Load Ratio','Wind Solar Load Ratio','0.00%'),('fact_market_hour','Timeline Negative Price Hours','Negative Price Hours','#,##0'),('fact_market_hour','Timeline Negative Price Share','Negative Price Hour Share','0.00%'),('fact_generation_hour','Timeline Capture Price','Capture Price EUR per MWh','0.00'),('fact_generation_hour','Timeline Capture Rate','Capture Rate','0.00%')]
 additions={'fact_market_hour':[], 'fact_generation_hour':[]}
 for home,name,base,fmt in wrappers:
  expression=f'''VAR SingleMonth = HASONEVALUE('report_month'[month_number])
VAR Grain = SELECTEDVALUE('report_axis'[grain])
VAR AxisMonth = SELECTEDVALUE('report_axis'[month_number])
VAR AxisDay = SELECTEDVALUE('report_axis'[day_number])
RETURN
    SWITCH(
        TRUE(),
        SingleMonth && Grain = "Day" && AxisMonth = SELECTEDVALUE('report_month'[month_number]),
            CALCULATE([{base}], TREATAS({{DATE(2025, AxisMonth, AxisDay)}}, 'dim_time_hour'[local_date])),
        NOT SingleMonth && Grain = "Month" && AxisMonth IN VALUES('report_month'[month_number]),
            CALCULATE([{base}], TREATAS({{AxisMonth}}, 'dim_time_hour'[month])),
        BLANK()
    )'''
  additions[home].append((name,expression,fmt,None))
 code="VAR SourceCode = SELECTEDVALUE('dim_generation_source'[generation_source_code])\nRETURN\n    LOOKUPVALUE('report_source'[source_color], 'report_source'[source_code], SourceCode)"
 additions['fact_generation_hour'] += [('Generation Source Color',code,None,None),('Generation Source Icon',code.replace('source_color','source_icon'),None,'ImageUrl')]
 for home,items in additions.items():
  p=MODEL/'tables'/f'{home}.tmdl';text=p.read_text()
  for name,expression,fmt,category in items:
   text=re.sub(r"\n\tmeasure '"+re.escape(name)+r"' =.*?(?=\n\t(?:measure|column|partition)\s|\Z)", "", text, flags=re.S)
   block=f"\tmeasure '{name}' =\n"+'\n'.join('\t\t\t'+line for line in expression.splitlines())+f'\n\t\tlineageTag: {uid(name)}\n\t\tdisplayFolder: Report presentation\n'
   if fmt:block+=f'\t\tformatString: {fmt}\n'
   if category:block+=f'\t\tdataCategory: {category}\n'
   text=text.replace('\n\tcolumn ','\n'+block+'\n\tcolumn ',1)
  p.write_text(text)
 config={'font':"'Avenir Next', Arial, sans-serif",'colors':COLORS,'sources':[{'code':c,'label':l,'color':fg,'icon':i} for c,l,fg,i in SOURCES],'axis_policy':'One selected month: daily; otherwise monthly. Fixed 2025 scope.','helper_tables':{'report_month':12,'report_axis':377,'report_source':12}}
 p=ROOT/'model/report_presentation.json';p.write_text(json.dumps(config,indent=2)+'\n')
 print('Built presentation tables and seven adaptive-axis measures; five gold partitions unchanged')

if __name__=='__main__':build()
