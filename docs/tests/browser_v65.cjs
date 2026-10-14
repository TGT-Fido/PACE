/* Optional browser validation. Run only against a disposable V6.5 test copy.
   Requirements: npm install playwright; npx playwright install chromium webkit.
   PACE_TEST_URL defaults to http://127.0.0.1:18765; PACE_BROWSER=webkit tests WebKit.
   This script is supplied for validation; it was NOT executed for this release. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 if(process.env.PACE_DISPOSABLE_TEST!=='yes')throw Error('Set PACE_DISPOSABLE_TEST=yes only for disposable test data.');
 const browser=await (process.env.PACE_BROWSER==='webkit'?webkit:chromium).launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true});
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.PACE_TEST_URL||'http://127.0.0.1:18765';
 const wait=()=>page.waitForFunction(()=>document.querySelector('#total').textContent!=='0');
 try{
 await page.goto(base);await wait();
 const getState=async()=>page.evaluate(async()=>await (await fetch('/api/state')).json());
 const noOverflow=async()=>assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 await noOverflow();assert.equal(await page.locator('.intro').count(),0);
 assert.deepEqual(await page.locator('.search-modes button').allTextContents(),['Overview + PDF contents','Overview']);
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 await page.getByRole('button',{name:'☀ Light',exact:true}).click();await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
 await page.getByLabel('Server display name').fill('Browser test server');await page.getByRole('button',{name:'Save name',exact:true}).click();
 await page.waitForFunction(async()=>((await (await fetch('/api/state')).json()).server_name)==='Browser test server');
 const slider=page.locator('#wallpaper-brightness');await slider.focus();await slider.press('Home');await slider.press('Tab');await page.waitForFunction(async()=>((await (await fetch('/api/state')).json()).brightness)===0);
 await slider.focus();await slider.press('End');await slider.press('Tab');await page.waitForFunction(async()=>((await (await fetch('/api/state')).json()).brightness)===100);
 await page.getByRole('button',{name:'Release notes',exact:true}).click();assert.equal(await page.locator('.release-entry[open]').count(),0);assert((await page.locator('.release-entry').count())>=5);
 await page.getByRole('button',{name:'Close dialog',exact:true}).click();
 await page.getByRole('button',{name:'Customize',exact:true}).click();await page.getByRole('button',{name:'Reorder projects',exact:true}).click();
 const before=await getState();await page.getByRole('button',{name:'+ Add page',exact:true}).click();const selects=page.locator('.reorder-row select');const last=await page.locator('.reorder-page').count();await selects.first().selectOption(String(last-1));
 await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.deepEqual((await getState()).card_pages,before.card_pages);
 await page.getByRole('button',{name:'Customize',exact:true}).click();await page.getByRole('button',{name:'Reorder projects',exact:true}).click();await page.getByRole('button',{name:'+ Add page',exact:true}).click();const n=await page.locator('.reorder-page').count();await page.locator('.reorder-row select').first().selectOption(String(n-1));await page.getByRole('button',{name:'Save',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#dialog').open);assert((await getState()).card_pages);
 for(const [width,height] of [[390,844],[844,390],[768,1024],[1024,768],[507,1024],[1920,1080]]){
 await page.setViewportSize({width,height});
 for(const layout of ['canvas','radial','roadmap']){
 await page.selectOption('#view-choice',layout);await page.locator('.map-surface').waitFor();await noOverflow();
 const zoom=await page.locator('.map-zoom').textContent();
 await page.getByRole('button',{name:'Expand workspace',exact:true}).click();assert(await page.locator('#map-view').evaluate(n=>n.classList.contains('workspace-expanded')));
 await page.getByRole('button',{name:'Restore workspace',exact:true}).click();assert.equal(await page.locator('.map-zoom').textContent(),zoom);
 if(width<=900){await page.getByRole('button',{name:'Project actions',exact:true}).click();assert(await page.locator('.map-action-sheet').evaluate(n=>n.open));await page.getByRole('button',{name:'Close actions',exact:true}).click();await page.getByRole('button',{name:'Map controls',exact:true}).click();assert(await page.getByRole('button',{name:'Move nodes',exact:true}).isVisible());}
 }
 }
 await page.selectOption('#view-choice','cards');await page.getByRole('button',{name:'Overview',exact:true}).click();await page.locator('#project-search').fill('Website');await page.waitForTimeout(350);assert((await page.locator('.card').count())>=1);
 await page.locator('.card .edit').first().click();assert.equal(await page.locator('#edit-category,#edit-priority').count(),0);await page.getByRole('button',{name:'Cancel',exact:true}).click();
 await page.locator('.card .primary').first().click();await page.locator('.annotationLayer input[type=checkbox]').first().waitFor();const box=page.locator('.annotationLayer input[type=checkbox]').first(),old=await box.isChecked();await box.click();await page.waitForFunction(()=>document.querySelector('#document-status').textContent==='Changes saved on the server');await page.reload();await page.locator('.annotationLayer input[type=checkbox]').first().waitFor();assert.equal(await page.locator('.annotationLayer input[type=checkbox]').first().isChecked(),!old);
 assert.deepEqual(errors,[]);console.log('PASS: browser interactions and viewport checks');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
