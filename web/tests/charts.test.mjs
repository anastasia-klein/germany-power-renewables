import test from 'node:test';
import assert from 'node:assert/strict';
import {columns,stacked} from '../charts.js';

function assertBarsInsidePlot(html){
  const grid=html.match(/<line x1="([\d.]+)" x2="([\d.]+)"/);
  assert.ok(grid,'A plot grid must be present');
  const left=Number(grid[1]),right=Number(grid[2]);
  const bars=[...html.matchAll(/<rect x="([\d.e+-]+)"[^>]* width="([\d.e+-]+)"/g)];
  assert.ok(bars.length>0,'The fixture must render bars');
  for(const [,x,width] of bars){
    assert.ok(Number(x)>left,'Bars must leave room beside the Y axis');
    assert.ok(Number(x)+Number(width)<right,'The final bar must stay inside the plot');
  }
}

test('single-period, monthly, hourly and daily columns stay clear of axis labels',()=>{
  for(const count of [1,2,12,24,31]){
    const rows=Array.from({length:count},(_,i)=>({label:String(i+1),value:i%2?-.2:1.1}));
    assertBarsInsidePlot(columns(rows,[{key:'value',label:'Capture rate',color:'#EFB63E'}],{percent:true,height:160}));
  }
});

test('stacked hourly bars also stay inside the plot with signed residual load',()=>{
  const rows=Array.from({length:24},(_,hour)=>({hour,solar:20,wind:15,residual:hour%2?-5:10,load:hour%2?30:45,n:30}));
  assertBarsInsidePlot(stacked(rows));
});
