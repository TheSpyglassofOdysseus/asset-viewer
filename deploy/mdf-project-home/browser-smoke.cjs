const http=require('http'),fs=require('fs'),path=require('path');
const {chromium}=require('/home/ubuntu/ironbeam-terminal-v3/vendor/openalgo-charts/node_modules/playwright');
const out='/home/ubuntu/.local/state/asset-viewer-project-home-20261019',root='/home/ubuntu/mdf-asset-viewer-private/characters',stage='/home/ubuntu/worktrees/asset-viewer-project-home-20261019/deploy/mdf-project-home';
const mime={'.html':'text/html','.json':'application/json','.js':'application/javascript','.css':'text/css','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.glb':'model/gltf-binary'};
const server=http.createServer((req,res)=>{
  let loc=new URL(req.url,'http://127.0.0.1'),p=decodeURIComponent(loc.pathname);
  if(p.startsWith('/asset-viewer/characters/')){
    let relative=p.slice('/asset-viewer/characters/'.length),f=path.resolve(relative.startsWith('projects/')?stage:root,relative.startsWith('projects/')?relative.slice('projects/'.length):relative);
    if(!(f===root||f.startsWith(root+'/')||f===stage||f.startsWith(stage+'/'))){res.writeHead(403);return res.end();}
    try{if(fs.statSync(f).isDirectory()) f=path.join(f,'index.html');const buffer=fs.readFileSync(f);res.writeHead(200,{'Content-Type':mime[path.extname(f)]||'application/octet-stream'});return res.end(buffer);}
    catch(e){res.writeHead(404);return res.end('missing '+p);}
  }
  if(p==='/asset-viewer/app.js'){
    return res.writeHead(200,{'Content-Type':'application/javascript'}).end(fs.readFileSync(stage+'/gallery-patched-preview.js'));
  }
  let upstream=p.startsWith('/asset-viewer')?p.slice('/asset-viewer'.length)||'/':p;
  const opts={hostname:'127.0.0.1',port:8167,path:upstream+loc.search,headers:{Host:'mdf-trading.duckdns.org','Accept-Encoding':'identity'}};
  http.get(opts,u=>{
    let chunks=[];u.on('data',c=>chunks.push(c));u.on('end',()=>{
      let b=Buffer.concat(chunks),ct=u.headers['content-type']||'application/octet-stream';
      if(ct.includes('json')||ct.includes('html')){
        let s=b.toString();
        if(ct.includes('html')) s=s.replaceAll('href="/app.css"','href="/asset-viewer/app.css"').replaceAll('src="/app.js"','src="/asset-viewer/app.js"').replace('<div class="rail-section-label">Collections</div>','<div class="rail-section-label">Production</div><nav class="collection-nav"><a href="/asset-viewer/characters/">100-character roster</a></nav><div class="rail-section-label">Collections</div>');
        s=s.replaceAll('"/asset/','"/asset-viewer/asset/').replaceAll('href="/asset/','href="/asset-viewer/asset/');
        b=Buffer.from(s);
      }
      const headers={'Content-Type':ct};res.writeHead(u.statusCode,headers);res.end(b);
    });
  }).on('error',e=>{res.writeHead(502);res.end(e.message);});
});
(async()=>{
 await new Promise(resolve=>server.listen(19184,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:'/snap/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']});
 for(const [name,url,width,height] of [
  ['projects-desktop','/asset-viewer/',1440,900],['gallery-desktop','/asset-viewer/c/aldric-helmet-options',1440,900],['roster-desktop','/asset-viewer/characters/',1440,900],
  ['projects-mobile','/asset-viewer/',390,844],['roster-mobile','/asset-viewer/characters/',390,844]
 ]){
  const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push('JS '+e.message));page.on('response',r=>{if(r.status()>=400)errors.push('HTTP '+r.status()+' '+r.url())});
  await page.goto('http://127.0.0.1:19184'+url,{waitUntil:'domcontentloaded',timeout:13000});
  try{await page.waitForTimeout(1300)}catch{}
  await page.screenshot({path:out+'/'+name+'.png',fullPage:false});
  const s=await page.evaluate(()=>({title:document.title,href:location.href,body:document.body.innerText.slice(0,1800),width:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,collectionButtons:document.querySelectorAll('#collectionNav [data-collection]').length,rosterButtons:document.querySelectorAll('#roster button.character').length,links:[...document.querySelectorAll('a[href]')].slice(0,15).map(a=>[a.innerText.trim().slice(0,40),a.getAttribute('href')])}));
  console.log(JSON.stringify({name,...s,errors:errors.slice(0,12)})); if(name.startsWith('projects')){if(!s.href.endsWith('/asset-viewer/characters/projects/')||!s.body.includes('GLOAM')||!s.body.includes('Project overview')||errors.length) throw Error('PROJECT_HOME_QA_FAILED '+name+' '+JSON.stringify(errors)); const initial=await page.evaluate(()=>({projects:document.querySelectorAll('.project-card').length,collections:document.querySelectorAll('#collectionList a').length,reviews:document.querySelectorAll('.review-row').length})); if(initial.projects!==6||initial.collections!==110||initial.reviews<1)throw Error('PROJECT_DATA_QA_FAILED '+name+' '+JSON.stringify(initial));await page.fill('#search','gloam');const filtered=await page.evaluate(()=>({projects:document.querySelectorAll('.project-card').length,collections:document.querySelectorAll('#collectionList a').length}));if(filtered.projects!==1||filtered.collections<0)throw Error('PROJECT_SEARCH_QA_FAILED '+name+' '+JSON.stringify(filtered));await page.fill('#search','');console.log('PROJECT_INTERACTION_PASS '+name+' '+JSON.stringify({initial,filtered}));} if(name.startsWith('gallery')&&(!s.body.includes('Project home')||s.collectionButtons!==110||errors.length))throw Error('GALLERY_COMPAT_QA_FAILED');
  await page.close();
 }
 await browser.close();server.close();
})().catch(e=>{console.error(e.stack);server.close();process.exitCode=1});
