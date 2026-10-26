// Read-only capture of the existing approved-scope pilot; never starts research.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(root, '.cache/playwright');
const { chromium } = require(path.join(root, 'frontend/node_modules/playwright'));
(async () => {
  const cfg = JSON.parse(fs.readFileSync(path.join(root, '.cache/auth-stage.json'), 'utf8'));
  const permit = JSON.parse(fs.readFileSync(path.join(root, '.cache/live-authorization.json'), 'utf8'));
  if (cfg.supabase_url !== 'http://127.0.0.1:57421') throw new Error('local only');
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  await context.addCookies([{name:'lather_session',value:cfg.users[0].token,url:'http://127.0.0.1:3140',httpOnly:true,sameSite:'Lax'}]);
  const response = await context.request.get('http://127.0.0.1:3140/api/workspace?run_id=' + permit.run_id);
  if (!response.ok()) throw new Error('workspace status ' + response.status());
  const data = await response.json();
  fs.mkdirSync(path.join(root, 'submission/assets'), {recursive:true});
  fs.writeFileSync(path.join(root,'.cache/live-workspace.json'),JSON.stringify(data,null,2));
  console.log(JSON.stringify({status:data.run?.status,report:data.report?.approval,review:data.report?.review?.decision,usage:data.usage}));
  const page = await context.newPage();
  for (const screen of ['shortlist','live','report']) {
    await page.goto('http://127.0.0.1:3140/' + screen + '?run=' + permit.run_id);
    await page.getByRole('heading',{level:1}).waitFor();
    await page.waitForTimeout(1800);
    await page.screenshot({path:path.join(root,'submission/assets/'+screen+'.png'), fullPage:true});
    console.log('Captured persisted LIVE '+screen+' screen.');
  }
  await browser.close();
})().catch(error=>{console.error('Read-only capture failed: '+error.message);process.exitCode=1;});
