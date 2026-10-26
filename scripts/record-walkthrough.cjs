// Read-only 210-second walkthrough of persisted LIVE evidence. No new run/approval.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'.cache/playwright');
const {chromium}=require(path.join(root,'frontend/node_modules/playwright'));
const segments=process.argv.includes('--final') ? [
  ['/report',30000,'Corrected LIVE report v4 passed independent review and was explicitly approved by the user. The immutable snapshot is saved; HTML and CSV exports are available. Unknown SKU normalization and unsupported opportunities remain unavailable.']
] : [
  ['/',25000,'Lather Lens helps a handmade-soap founder research competitors. This recording shows one persisted LIVE run; it does not start another paid search.'],
  ['/shortlist',30000,'Scout: Tavily discovery, model-assisted relevance and evidence checks. Fika Soaps and Forest Essentials were approved by the user. A third brand was not invented.'],
  ['/live',30000,'LangGraph coordinates independent research lanes. Postgres stores events, checkpoints and approval state. Completed research survived interruption and targeted correction.'],
  ['/report',35000,'The report separates source claims, interpretations and hypotheses. Fireworks is the provisional pilot provider; a benchmark winner has not been selected.'],
  ['/report#compare',30000,'Listed prices and product descriptions remain attributable. Unknown SKU/pack bindings prevent a fabricated price-per-100g calculation. Missing evidence stays visible.'],
  ['/report#sources',30000,'Evidence retains URLs, retrieval times, excerpts and hashes. Citation presence is not proof of genuine support. Independent review identified unsupported wording and required correction.'],
  ['/report',30000,'The final report requires human approval before saving/export. No deployment or competitor contact occurs. Owner usefulness and full material-claim support are not yet measured.']
];
(async()=>{
  const cfg=JSON.parse(fs.readFileSync(path.join(root,'.cache/auth-stage.json'),'utf8'));
  const permit=JSON.parse(fs.readFileSync(path.join(root,'.cache/live-authorization.json'),'utf8'));
  if(cfg.supabase_url!=='http://127.0.0.1:57421')throw new Error('local only');
  const browser=await chromium.launch();
  const context=await browser.newContext({viewport:{width:1366,height:900},reducedMotion:'reduce',recordVideo:{dir:path.join(root,'submission/video'),size:{width:1366,height:900}}});
  await context.addCookies([{name:'lather_session',value:cfg.users[0].token,url:'http://127.0.0.1:3140',httpOnly:true,sameSite:'Lax'}]);
  const page=await context.newPage();
  let index=0;
  for(const [route,duration,caption] of segments){
    const [pathname,anchor]=route.split('#');
    await page.goto('http://127.0.0.1:3140'+pathname+(pathname==='/'?'':'?run='+permit.run_id)+(anchor?'#'+anchor:''));
    await page.getByRole('heading',{level:1}).waitFor();
    await page.waitForTimeout(1200);
    if(anchor)await page.locator('#'+anchor).scrollIntoViewIfNeeded();
    if(index===3)await page.getByRole('heading',{name:'AI research briefing'}).scrollIntoViewIfNeeded();
    await page.evaluate(({caption,index})=>{
      const el=document.createElement('div');el.id='recording-caption';
      el.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#102d25f5;color:white;padding:16px 28px;font:20px/1.5 Arial;border-top:4px solid #dbf383;box-shadow:0 -2px 16px #0003';
      const label=document.createElement('div');label.style.cssText='font-size:12px;color:#dbf383;margin-bottom:4px';label.textContent='LATHER LENS | PERSISTED LIVE RUN | '+(index+1)+'/7';
      const text=document.createElement('div');text.textContent=caption;el.append(label,text);document.body.append(el);
    },{caption,index});
    console.log('Recording segment '+(++index)+'/7 (read-only).');
    await page.waitForTimeout(duration);
  }
  const video=page.video();await context.close();
  await video.saveAs(path.join(root,process.argv.includes('--final')?'submission/Lather-Lens-final-segment.webm':'submission/Lather-Lens-walkthrough.webm'));
  await browser.close();
  console.log('PASS captioned walkthrough saved. Target timeline 210 seconds plus navigation; trim to 210 seconds for submission. No audio track.');
})().catch(e=>{console.error('Recording failed: '+e.message);process.exitCode=1;});
