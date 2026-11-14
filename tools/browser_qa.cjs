// Optional browser QA: PLAYWRIGHT_MODULE can point to an installed Playwright package.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');const path=require('node:path');
(async()=>{
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base=process.env.BASE_URL||'http://127.0.0.1:8765';const root=path.resolve(__dirname,'..');let checks=[];
function check(value,label){if(!value)throw Error(label);checks.push(label);console.log('PASS',label);}
await page.goto(base);await page.getByRole('heading',{name:'What is the market weather today?'}).waitFor({timeout:60000});
check(await page.getByRole('heading',{name:'VIX / The market stress lens'}).count()===1,'Homepage includes official VIX history');
check(await page.locator('html').getAttribute('lang')==='en','Document language is English');
await page.screenshot({path:path.join(root,'preview-desktop.png'),fullPage:true});
await page.locator('nav [data-view="explorer"]').click();await page.getByRole('heading',{name:'SPY / Adjusted price and moving averages'}).waitFor();
await page.locator('#symbol').fill('AAPL');await page.locator('#loadAsset').click();await page.getByRole('heading',{name:'AAPL / Adjusted price and moving averages'}).waitFor();check(true,'Asset search loads AAPL');
await page.locator('nav [data-view="lab"]').click();
for(const strategy of ['trend','momentum','reversion','volatility','rate_guard']){await page.locator('#strategy').selectOption(strategy);await page.locator('#run').click();await page.locator('#export').waitFor();check((await page.locator('.metricGrid .card').count())===8,`${strategy} historical backtest exposes all 8 metrics`);}
const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export').click()]);await download.saveAs(path.join(root,'reports','browser-export-rate-aware.json'));const result=JSON.parse(fs.readFileSync(path.join(root,'reports','browser-export-rate-aware.json')));check(result.rate_source.symbol==='^IRX','Export retains short-yield provenance');check(result.rate_alignment.every(r=>!r.rate_date||r.rate_date<r.date),'Every rate observation precedes its signal date');
await page.screenshot({path:path.join(root,'preview-backtest.png'),fullPage:true});
await page.locator('nav [data-view="worlds"]').click();await page.locator('#shock').fill('-100');await page.locator('#shock').dispatchEvent('input');check((await page.locator('#impact').innerText()).includes('+7.00%'),'Duration scenario: -100 bps gives +7% for D=7');
await page.locator('nav [data-view="news"]').click();check(await page.locator('article a').count()>0,'Official policy-news links present');
await page.locator('nav [data-view="sources"]').click();check(await page.locator('tbody tr').count()===25,'All 25 asset provenance records visible');
await page.locator('nav [data-view="politics"]').click();await page.locator('#exportEvent').waitFor();await page.locator('#eventSectors tbody tr').first().waitFor();check(await page.locator('#eventSectors tbody tr').count()===11,'Eleven sector event windows calculated');
check((await page.locator('#eventResult').innerText()).includes('PARTIAL WINDOW'),'Unfinished 2026 post-election window is labelled partial');
check(await page.getByRole('link',{name:'BBC News',exact:false}).count()>0,'Political feed visibly credits BBC News');
await page.screenshot({path:path.join(root,'preview-politics.png'),fullPage:true});
for(const event of ['2022-midterms','2018-midterms']){await page.locator('#event').selectOption(event);await page.locator('#study').click();await page.locator('#exportEvent').waitFor();await page.locator('#eventSectors tbody tr').first().waitFor();check((await page.locator('#eventResult').innerText()).includes('Full +20-session window available.'),`${event} complete historical window verified`);}
await page.locator('nav [data-view="global"]').click();await page.locator('#exportGlobal').waitFor();check(await page.locator('.marketCard').count()===10,'Ten representative index cards are visible');check((await page.locator('#globalBody').innerText()).includes('FTSE 100'),'UK market is included in the representative-index view');check(!(await page.locator('#globalBody').innerText()).includes('Domestic market cap'),'Exchange-capitalization ranking has been replaced');await page.screenshot({path:path.join(root,'preview-global.png'),fullPage:true});await page.locator('[data-global-symbol="^GSPC"]').click();await page.getByRole('heading',{name:'^GSPC / Adjusted price and moving averages'}).waitFor();check((await page.locator('#assetBody').innerText()).includes('Indicator only'),'Index exploration does not imply an investable signal');await page.setViewportSize({width:390,height:844});
for(const view of ['overview','global','explorer','lab','worlds','news','sources','politics']){await page.locator(`nav [data-view="${view}"]`).click();if(view==='global')await page.locator('#exportGlobal').waitFor();if(view==='explorer')await page.locator('#assetBody .grid4').waitFor();if(view==='politics'){await page.locator('#exportEvent').waitFor();await page.locator('#eventSectors tbody tr').first().waitFor();}check(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`${view} fits mobile viewport`);check(!/[\u3400-\u9fff]/.test(await page.locator('body').innerText()),`${view} has no untranslated Chinese UI`);}
await page.locator('nav [data-view="overview"]').click();await page.screenshot({path:path.join(root,'preview-mobile.png'),fullPage:true});
check(errors.length===0,'No browser JavaScript errors');fs.writeFileSync(path.join(root,'reports','browser-qa.json'),JSON.stringify({checked_at:new Date().toISOString(),checks,errors},null,2));
await browser.close();console.log(`${checks.length} browser checks passed`);
})().catch(e=>{console.error(e);process.exit(1);});
