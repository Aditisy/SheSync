const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error'&&!message.text().includes('400'))errors.push(message.text())});
 await page.goto('http://localhost:5000');try{await page.waitForFunction(()=>typeof api==='function');}catch(error){throw Error(JSON.stringify(errors));}
 const user=await page.evaluate(()=>api('/api/auth/signup',{method:'POST',body:JSON.stringify({name:'Fallback browser check',email:'fallback-'+Date.now()+'@example.test',password:'test-only-browser-password'})}));
 await page.evaluate(account=>{LS.set('ss_session',account);secureAccount=true;loadApp();},user);
 await page.evaluate(()=>switchTab('doctors'));
 await page.fill('#doctor-city','Bengaluru');await page.fill('#doctor-area','Mallathahalli');await page.selectOption('#doctor-specialty','Gynecologist');
 await page.click('#city-button');await page.waitForFunction(()=>!document.getElementById('city-button').disabled,{timeout:20000});
 const mapsHref=await page.getAttribute('#maps-fallback','href');
 if(!mapsHref.includes('google.com/maps/search')||!mapsHref.includes('Mallathahalli'))throw Error('No-query Google Maps fallback');
 if((await page.textContent('#doctor-status')).match(/403|permission_denied|http/i))throw Error('Raw provider error exposed');
 const liveCards=await page.locator('#doctors-list .doctor-card').count();
 await page.click('.manual-clinic summary');await page.fill('#manual-clinic-name','Presentation clinic');await page.fill('#manual-specialty','Gynecology');await page.fill('#manual-address','Verified from a clinic listing');await page.click('button[onclick="prepareManualAppointment()"]');
 await page.fill('#appointment-day',new Date(Date.now()+2*86400000).toISOString().slice(0,10));await page.fill('#appointment-time','10:30');await page.fill('#appointment-reason','Cycle consultation');await page.fill('#appointment-contact-name','Fallback browser check');await page.fill('#appointment-contact-phone','+919000000000');
 await page.click('#appointment-form button[type="submit"]');await page.waitForFunction(()=>document.getElementById('appointments-list').textContent.includes('Request prepared'));
 const records=await page.evaluate(()=>api('/api/appointments'));if(records.length!==1||records[0].reason!=='Cycle consultation'||records[0].status!=='request_prepared')throw Error('Appointment persistence shape is wrong');
 await page.reload();await page.waitForFunction(()=>secureAccount);await page.evaluate(()=>switchTab('doctors'));await page.waitForFunction(()=>document.getElementById('appointments-list').textContent.includes('Cycle consultation'));
 const bad=await page.evaluate(()=>api('/api/appointments',{method:'POST',body:JSON.stringify({clinic:{name:'Bad'},day:'2000-01-01',time:'10:00',reason:'x',contact_name:'x',contact_phone:'bad'})}).then(()=>null,e=>e.message));if(!bad||!bad.includes('Choose a preferred date'))throw Error('Past date was accepted');
 const id=(await page.evaluate(()=>api('/api/appointments')))[0].id;await page.evaluate(id=>api('/api/appointments/'+id,{method:'DELETE'}),id);if((await page.evaluate(()=>api('/api/appointments')))[0].status!=='cancelled')throw Error('Cancellation did not persist');
 await page.screenshot({path:'doctor-fallback-browser.png',fullPage:true});
 const report={mapsFallback:true,liveCards,manualClinic:true,persistedAfterReload:true,pastDateRejected:true,cancelled:true,javascriptErrors:errors};fs.writeFileSync('tests/DOCTOR_FALLBACK_REPORT.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();if(errors.length)process.exitCode=1;
})().catch(error=>{console.error(error);process.exit(1)});
