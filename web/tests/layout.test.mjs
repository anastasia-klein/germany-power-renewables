import test from 'node:test';
import assert from 'node:assert/strict';
import {reportLayout,REPORT_SIZE} from '../layout.js';

test('the desktop sheet fits both viewport axes without changing its proportions',()=>{
  for(const [width,height] of [[1000,560],[1280,620],[1280,720],[1366,768],[1440,900],[1920,1080],[2560,1440]]){
    const layout=reportLayout(width,height);
    assert.ok(layout.width+2*REPORT_SIZE.gutter<=width+1e-8);
    assert.ok(layout.height+2*REPORT_SIZE.gutter<=height+1e-8);
    assert.ok(layout.scale>0&&layout.scale<=1);
    assert.ok(Math.abs(layout.width/layout.height-REPORT_SIZE.width/REPORT_SIZE.height)<1e-8);
  }
});

test('phones, very short windows and expanded methodology retain natural scrolling',()=>{
  for(const [width,height,expanded] of [[390,844,false],[999,800,false],[1366,559,false],[1440,900,true]]){
    assert.equal(reportLayout(width,height,expanded),null);
  }
});
