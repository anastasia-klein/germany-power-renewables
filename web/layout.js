// Keep every desktop report page on the same sheet, fitted to both window axes.
export const REPORT_SIZE = Object.freeze({width:1600,height:960,gutter:12});

export function reportLayout(width,height,expanded=false){
  if(expanded||width<1000||height<560)return null;
  const {width:sheetWidth,height:sheetHeight,gutter}=REPORT_SIZE;
  const scale=Math.min(1,(width-2*gutter)/sheetWidth,(height-2*gutter)/sheetHeight);
  return {scale,width:sheetWidth*scale,height:sheetHeight*scale};
}

export function fitReport(){
  const frame=document.querySelector('.report-frame');
  if(!frame)return;
  const layout=reportLayout(window.innerWidth,window.innerHeight,!!document.querySelector('.about[open]'));
  document.body.classList.toggle('fit-report',!!layout);
  if(layout){
    frame.style.setProperty('--report-scale',layout.scale);
    frame.style.setProperty('--frame-width',`${layout.width}px`);
    frame.style.setProperty('--frame-height',`${layout.height}px`);
  }else frame.removeAttribute('style');
}

if(typeof window!=='undefined')window.addEventListener('resize',fitReport);
