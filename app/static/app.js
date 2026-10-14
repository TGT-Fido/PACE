'use strict';
import {setHDR, hdrHelp, hdrStatus} from '/hdr.js';
import {createMaps} from '/maps.js';
import {createWorkspace} from '/workspace.js';
const $=s=>document.querySelector(s);
let state, page=1, loading=false, documentViewer=null, currentDocument=null, activeRoute='';
let pendingRoute=false;
let refreshFinished=Promise.resolve(),releaseRefresh;
const palette={'Teal':'#4db7c2','Purple':'#a17cde','Green':'#75be8a','Blue':'#689edd','Orange':'#e4a46b','Pink':'#dc86b1','Yellow':'#d5bd6a','Gray':'#9ba4b4'};
const defaults={'D&D':'Purple','Home':'Orange','Smart Home':'Green','Cars':'Blue','Audio':'Pink','Learning':'Yellow'};
const chosenColor=p=>p.color||palette[defaults[p.category]||'Teal'];
const cardColor=p=>['On hold','Cancelled'].includes(p.status)?palette.Gray:chosenColor(p);
const colorName=c=>state?.colors?.[c]||Object.keys(palette).find(k=>palette[k]===c)||c;
let searchResult=null, searchSerial=0, searchTimer, searchPoll;


const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const button=(text,fn,cls)=>{const n=el('button',text,cls);n.type='button';n.onclick=fn;return n};
const link=(text,url,cls)=>{const n=el('a',text,cls);n.href=url;return n};
async function refresh(manual=false){
  if(loading){await refreshFinished;return refresh(manual)} loading=true;refreshFinished=new Promise(resolve=>releaseRefresh=resolve);
  const started=performance.now(); $('#refresh').disabled=true;
  $('#refresh').classList.add('refreshing'); $('#refresh').setAttribute('aria-busy','true');
  $('#refresh-label').textContent='Scanning…';
  try{
    const r=await fetch('/api/state'); if(!r.ok)throw Error('Server unavailable');
    state=await r.json(); $('#error').hidden=true;
    $('#sync').textContent=(manual?'Last checked ':'Last checked ')+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    render();
  }catch(e){
    $('#error').textContent='Could not refresh. Your last view is retained. Check that PACE is running, then retry.';
    $('#error').hidden=false; $('#sync').textContent='Refresh failed · Try again';
  }finally{
    if(manual)await new Promise(resolve=>setTimeout(resolve,Math.max(0,550-(performance.now()-started))));
    loading=false; releaseRefresh(); $('#refresh').disabled=false; $('#refresh').classList.remove('refreshing');
    $('#refresh').setAttribute('aria-busy','false'); $('#refresh-label').textContent='Rescan';
  }
}
function documentRoute(p,f){return '#document/'+encodeURIComponent(p.id)+'/'+encodeURIComponent(f.name)}
function documentLink(p,f,text,cls){const a=link(text,documentRoute(p,f),cls);a.addEventListener('click',()=>$('#dialog').close());return a}
async function ensureViewer(){
  if(!documentViewer){const module=await import('/viewer.js');documentViewer=module.createDocumentViewer(()=>state.token);}
  return documentViewer;
}
async function route(){
  if(!state||pendingRoute)return;
  const requested=location.hash;
  if(requested===activeRoute)return;
  pendingRoute=true;
  try{
    if(documentViewer&&!(await documentViewer.canLeave())){
      window.history.replaceState(null,'',activeRoute||location.pathname);return;
    }
    const match=/^#document\/([^/]+)\/(.+)$/.exec(requested);
    if(match){
      const pid=decodeURIComponent(match[1]),parts=match[2].split('?page='),filename=decodeURIComponent(parts[0]);const targetPage=Number(parts[1])||1;
      const project=state.projects.find(p=>p.id===pid),file=project?.files.find(f=>f.name===filename);
      if(!file)throw Error('This project PDF is missing. Refresh folders or restore the file.');
      $('#dialog').close();$('#dashboard').hidden=true;$('#document-view').hidden=false;
      document.body.classList.add('reading'); currentDocument={project,file};
      const viewer=await ensureViewer();await viewer.open(project,file);if(targetPage>1){$('#page-number').value=targetPage;$('#page-number').dispatchEvent(new Event('change'));}window.scrollTo(0,0);
    }else{
      if(documentViewer)await documentViewer.close();
      currentDocument=null;$('#dashboard').hidden=false;$('#document-view').hidden=true;
      document.body.classList.remove('reading');render();
    }
    activeRoute=requested;
  }catch(error){
    $('#dashboard').hidden=false;$('#document-view').hidden=true;document.body.classList.remove('reading');
    $('#error').textContent=error.message;$('#error').hidden=false;window.history.replaceState(null,'',location.pathname);activeRoute='';
  }finally{pendingRoute=false;if(location.hash!==activeRoute&&location.hash.startsWith('#document/'))route();}
}
async function dismissAmbiguities(p){
  try{
    const r=await fetch('/api/project',{method:'POST',headers:{'Content-Type':'application/json','X-PACE-Token':state.token},body:JSON.stringify({id:p.id,dismiss_ambiguities:true})});
    if(!r.ok)throw Error('Could not dismiss warning.');await refresh();
  }catch(e){$('#error').textContent=e.message;$('#error').hidden=false;}
}
function warning(p,text){
  const n=el('div',undefined,'note');n.append(el('span',text));
  if(text===p.ambiguity_message)n.append(button('Dismiss',()=>dismissAmbiguities(p),'dismiss'));
  return n;
}
function projectIcon(category){
  const icons={
    'Music':'<path d="M12 25V8l15-4v17 M12 12l15-4"/><ellipse cx="8" cy="25" rx="4" ry="3"/><ellipse cx="23" cy="21" rx="4" ry="3"/>',
    'Travel':'<path d="m3 17 10-3L24 3l4 1-7 11 9 2v3l-12 1-5 8-3-1 2-8-9-1Z"/>',
    'Art':'<path d="M16 3C-1 3 1 27 14 29c8 1 0-7 6-7C34 23 31 3 16 3Z"/><circle cx="10" cy="11" r="1"/><circle cx="18" cy="8" r="1"/><circle cx="24" cy="13" r="1"/>',
    'Fitness':'<path d="M4 10v12 M9 7v18 M23 7v18 M28 10v12 M9 16h14"/>',
    'Work':'<rect x="3" y="10" width="26" height="19" rx="3"/><path d="M11 10V4h10v6 M3 18h26 M13 16v5h6v-5"/>',
    'Nature':'<path d="M6 26C-1 13 12 3 28 4c-1 17-10 27-22 22Z M4 29 22 10"/>',
    'Science':'<path d="M11 3h10 M13 3v10L4 26q-1 3 3 3h18q4 0 3-3l-9-13V3 M8 21h16"/>',
    'Camera':'<rect x="3" y="9" width="26" height="20" rx="3"/><path d="M10 9 12 4h8l2 5"/><circle cx="16" cy="19" r="6"/>',
    'Coffee':'<path d="M5 12h17v10q0 7-8 7t-9-7Z M22 14h3q7 0 3 7h-6 M9 3v5 M16 2v6"/>',

    'D&D':'<path d="m16 3 12 7v12l-12 7L4 22V10Z M16 3v26 M4 10l24 12 M28 10 4 22 M4 10h24 M4 22h24"/>',
    'Home':'<path d="m3 15 13-11 13 11 M7 13v15h7v-9h5v9h6V13"/>',
    'Smart Home':'<path d="m3 15 13-11 13 11 M7 13v15h7v-9h5v9h6V13"/>',
    'Cars':'<circle cx="16" cy="16" r="12"/><circle cx="16" cy="16" r="4"/><path d="M4 14h8 M28 14h-8 M16 20v8"/>',
    'Audio':'<path d="M16 7v22 M16 7C12 3 5 3 3 5v21c5-2 9-1 13 3 M16 7c4-4 11-4 13-2v21c-5-2-9-1-13 3"/>',
    'Learning':'<path d="m2 11 14-7 14 7-14 7Z M7 14v10c6 5 12 5 18 0V14 M30 11v13"/>',
    'Technology':'<rect x="5" y="3" width="22" height="7" rx="2"/><rect x="5" y="13" width="22" height="7" rx="2"/><rect x="5" y="23" width="22" height="7" rx="2"/><path d="M9 6h1 M9 16h1 M9 26h1 M19 6h4 M19 16h4 M19 26h4"/>'
  };
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 32 32');svg.setAttribute('aria-hidden','true');svg.innerHTML=icons[category]||icons.Technology;
  const box=el('span',undefined,'project-icon');box.append(svg);return box;
}
async function save(id,changes,move){const r=await fetch('/api/project',{method:'POST',headers:{'Content-Type':'application/json','X-PACE-Token':state.token},body:JSON.stringify(move===undefined?{id,changes}:{id,move})});const data=await r.json();if(!r.ok)throw Error(data.error||'Save failed');await refresh();}
function filterOptions(selector,values,label){const s=$(selector),value=s.value;s.replaceChildren(new Option(label,''));for(const v of [...new Set(values)].sort())s.add(new Option(v,v));s.value=values.includes(value)?value:'';}
function render(){const cfg=state.config;$('#app-version').textContent='v'+state.version;
const bg=state.background;document.body.style.setProperty('--custom-background',bg&&/^\/background\/[^/]+\.(png|jpg|jpeg|webp)$/i.test(bg)?`url("${bg}")`:'none');document.body.classList.toggle('custom-background',!!bg);document.body.style.setProperty('--wallpaper-shade',String(1-(state.brightness??75)/100));
$('#title').textContent='PACE';$('#year').textContent=cfg.year;document.title=$('#title').textContent+' · Projects At a glanCE';$('#total').textContent=state.projects.length;
filterOptions('#category',state.categories,'All categories');filterOptions('#status',state.statuses,'All statuses');filterOptions('#badge-filter',state.badges,'All badges');
filterOptions('#color-filter',state.projects.map(cardColor),'All colors');for(const opt of $('#color-filter').options)if(opt.value)opt.textContent=colorName(opt.value);
$('#warnings').replaceChildren(...state.warnings.map(w=>el('p',w,'note')));
const filtered=state.projects.filter(p=>matchesSearch(p)&&(!$('#category').value||p.category===$('#category').value)&&(!$('#status').value||p.status===$('#status').value)&&(!$('#badge-filter').value||(p.badges||[]).includes($('#badge-filter').value))&&(!$('#color-filter').value||cardColor(p)===$('#color-filter').value));
const size=Math.max(1,Math.min(24,Number(cfg.page_size)||8)), groups=workspace.pages(filtered), pages=groups.length;page=Math.max(1,Math.min(page,pages));
$('#range').textContent=filtered.length?`${groups[page-1].length} of ${filtered.length} projects · Page ${page}/${pages}`:'No matching projects';
$('#cards').replaceChildren(...groups[page-1].map(card));if(!filtered.length)$('#cards').append(el('p','No projects match these filters.','empty'));
const nav=$('#pagination');nav.replaceChildren();const prev=button('← Previous',()=>{page--;render();window.scrollTo(0,0)});prev.disabled=page===1;nav.append(prev);for(let i=1;i<=pages;i++){const b=button(String(i),()=>{page=i;render();window.scrollTo(0,0)},page===i?'selected':'');b.setAttribute('aria-label','Page '+i);if(page===i)b.setAttribute('aria-current','page');workspace.pageDrop(b,i-1);nav.append(b)}const next=button('Next →',()=>{page++;render();window.scrollTo(0,0)});next.disabled=page===pages;nav.append(next);maps.sync(state,filtered);workspace.sync();}
function card(p){const colors={'D&D':'dnd','Home':'home','Smart Home':'smart','Cars':'cars','Learning':'learning','Audio':'audio'};const c=el('article',undefined,'card cat-'+(colors[p.category]||'tech')+(/on hold|cancelled/i.test(p.status)?' parked':''));
c.style.setProperty('--accent',cardColor(p));c.dataset.projectId=p.id;
const top=el('div',undefined,'cardtop');const heading=el('div',undefined,'card-heading');heading.append(el('span',p.category,'category'),el('h3',p.name));const icon=button('',()=>iconPicker(p),'icon-button');icon.setAttribute('aria-label','Change icon for '+p.name);if(p.icon?.startsWith('/icon/')){const img=el('img');img.src=p.icon;img.alt='';icon.append(img)}else icon.append(projectIcon(p.icon||p.category));top.append(icon,heading,button('•••',()=>projectMenu(p),'edit'));top.lastChild.setAttribute('aria-label','Actions for '+p.name);
c.append(top,el('p',p.summary,'summary'));
const mile=el('div',undefined,'milestone');mile.append(el('small','NEXT MILESTONE'),el('p',p.milestone||'Set a next milestone.'));c.append(mile,el('p',p.priority,'priority'));
for(const w of p.warnings)c.append(warning(p,w));
const statusRow=el('div',undefined,'statusrow');statusRow.append(el('span',p.status,'badge status-badge status-'+p.status.toLowerCase().replaceAll(' ','-')));if(p.detail)statusRow.append(el('span',p.detail,'badge detail-badge'));for(const b of p.badges||[])statusRow.append(el('span',b,'badge custom-badge'));c.append(statusRow);
const f=el('div',undefined,'file');f.append(el('strong',p.active?`${p.active.label} · ${p.pin?'Pinned':'Automatic/latest'}`:p.files.length?'Selection needed':p.missing?'Folder missing':'No PDF yet'));if(p.active)f.append(el('span',p.active.name));else if(!p.files.length&&!p.missing)f.append(el('span','Add a PDF to this project folder.'));c.append(f);
const acts=el('div',undefined,'actions');if(p.active)acts.append(documentLink(p,p.active,'View project →','button primary'));else{const b=button(p.files.length?'Choose PDF →':'No PDF yet',()=>history(p));b.disabled=!p.files.length;acts.append(b)}acts.append(button('History · '+p.files.length,()=>history(p)),button('Upload PDF',()=>uploadDialog(p)));c.append(acts);
workspace.cardDrag(c,p);const order=el('div',undefined,'order');order.append(el('span',p.source==='Starter / unconfirmed'?'Starter / unconfirmed':p.missing?'Missing folder':''));for(const [label,delta] of [['←',-1],['→',1],['↑',-Math.max(1,getComputedStyle($('#cards')).gridTemplateColumns.split(' ').length)],['↓',Math.max(1,getComputedStyle($('#cards')).gridTemplateColumns.split(' ').length)]]){const b=button(label,()=>save(p.id,null,label==='↑'?-Math.max(1,getComputedStyle($('#cards')).gridTemplateColumns.split(' ').length):label==='↓'?Math.max(1,getComputedStyle($('#cards')).gridTemplateColumns.split(' ').length):delta).catch(e=>{const box=open('Could not move project');box.append(el('p',e.message))}));b.dataset.project=p.id;b.dataset.direction=label;b.setAttribute('aria-label','Move '+p.name+' '+({'←':'left','→':'right','↑':'up','↓':'down'}[label]));b.disabled=state.projects.indexOf(p)+delta<0||state.projects.indexOf(p)+delta>=state.projects.length;order.append(b)}c.append(order);c.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();e.stopPropagation();c.classList.add('drop-active')}});c.addEventListener('dragleave',()=>c.classList.remove('drop-active'));c.addEventListener('drop',e=>{e.preventDefault();e.stopPropagation();c.classList.remove('drop-active');bulkImport(p.id,[...e.dataTransfer.files])});return c;}
function open(title){$('#dialogtitle').textContent=title;$('#dialogbody').replaceChildren();$('#dialogerror').textContent='';if(!$('#dialog').open)$('#dialog').showModal();return $('#dialogbody');}
function edit(p){
 const body=open('Edit '+p.name),form=el('form');body.append(button('Relationships',()=>maps.relations(p.id)));
 for(const [key,label] of [['name','Project name'],['status','Status'],['detail','Detail badge (optional)'],['summary','Summary'],['milestone','Next milestone']]){
  const l=el('label',label),input=el(['summary','milestone'].includes(key)?'textarea':['category','status'].includes(key)?'select':'input');
  input.name=key;input.id='edit-'+key;l.htmlFor=input.id;
  if(key==='status')for(const value of state.statuses)input.add(new Option(value,value));
  if(key==='category')for(const value of state.categories)input.add(new Option(value,value));
  input.value=p[key]||'';input.maxLength=key==='detail'?160:2000;if(['name','category','status'].includes(key))input.required=true;form.append(l,input);
 }
 const cl=el('label','Card accent'),color=el('select');color.id='edit-color';cl.htmlFor=color.id;color.add(new Option('Automatic/category default',''));
 for(const [value,name] of Object.entries(state.colors))color.add(new Option(name,value));if(p.color&&!Object.values(palette).includes(p.color))color.add(new Option(p.color,p.color));color.value=p.color||'';
 const custom=el('input');custom.type='color';custom.id='custom-color';custom.value=chosenColor(p);custom.setAttribute('aria-label','Custom accent color');custom.oninput=()=>{if(![...color.options].some(o=>o.value===custom.value))color.add(new Option(custom.value,custom.value));color.value=custom.value;};form.append(cl,color,custom);
 const swatches=el('div',undefined,'swatches');
 for(const [name,value] of Object.entries(state.presets)){const sw=button('',()=>{custom.value=value;custom.oninput();colorLabel.value=colorName(value);},'swatch');sw.style.background=value;sw.title=colorName(value);sw.setAttribute('aria-label',colorName(value));swatches.append(sw)}
 const colorLabel=el('input');colorLabel.id='color-name';colorLabel.placeholder='Name this color, e.g. Atomic Blue';colorLabel.maxLength=80;colorLabel.value=p.color?(state.colors[p.color]||''):'';colorLabel.setAttribute('aria-label','Color name');
 const oldInput=custom.oninput;custom.oninput=()=>{oldInput();colorLabel.value=state.colors[custom.value]||'';};color.onchange=()=>{if(color.value)custom.value=color.value;colorLabel.value=state.colors[color.value]||'';};
 form.append(swatches,el('label','Color name (used in filters)'),colorLabel,el('p','Renaming a color updates its label for every card using that exact color.','muted'));
 const badges=el('fieldset');badges.append(el('legend','Custom badges'));
 for(const badge of state.badges){const label=el('label',undefined,'badge-option'),check=el('input');check.type='checkbox';check.value=badge;check.checked=(p.badges||[]).includes(badge);label.append(check,document.createTextNode(badge));badges.append(label)}
 badges.append(el('p','Create or rename badges using Customize at the top of the dashboard.','muted'));form.append(badges);
 form.append(el('p','Folder: '+p.folder+' · Renaming the card does not rename its folder.','muted'));
 const actions=el('div',undefined,'formbuttons');actions.append(button('Cancel',()=>$('#dialog').close()));const submit=el('button','Save changes');submit.type='submit';actions.append(submit);form.append(actions);
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{const changes=Object.fromEntries(new FormData(form));changes.color=color.value||null;changes.badges=[...badges.querySelectorAll('input:checked')].map(n=>n.value);if(changes.color&&colorLabel.value.trim())await setting({kind:'color',value:changes.color,name:colorLabel.value.trim()});await save(p.id,changes);$('#dialog').close()}catch(err){$('#dialogerror').textContent=err.message}finally{submit.disabled=false}};
 body.append(form);
}
async function setting(body){const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-PACE-Token':state.token},body:JSON.stringify(body)});const result=await r.json();if(!r.ok)throw Error(result.error||'Could not save');await refresh();}
function customize(){
 const body=open('Customize PACE');body.append(button('Reorder projects',()=>workspace.reorder()),el('p','Categories, badges, colors and project order are shared by your devices.','muted'));workspace.appearance(body);
 for(const kind of ['category','badge']){
  const section=el('section',undefined,'settings-section');section.append(el('h3',kind==='category'?'Categories':'Custom badges'));
  const form=el('form',undefined,'new-entry'),input=el('input');input.placeholder=kind==='category'?'New category':'New badge';input.setAttribute('aria-label',input.placeholder);input.maxLength=80;input.required=true;const add=el('button','Add');add.type='submit';form.append(input,add);
  form.onsubmit=async e=>{e.preventDefault();add.disabled=true;try{await setting({kind,action:'add',name:input.value});customize()}catch(err){$('#dialogerror').textContent=err.message}finally{add.disabled=false}};section.append(form);
  for(const name of state[kind==='category'?'categories':'badges']){
   const row=el('div',undefined,'taxonomy-row');row.append(el('span',name));
   if(!(kind==='category'&&name==='Other')){
    row.append(button('Rename',()=>{const pane=open('Rename '+name),f=el('form'),field=el('input'),label=el('label','New name');field.id='rename-entry';label.htmlFor=field.id;field.value=name;field.maxLength=80;field.required=true;const submit=el('button','Save name');submit.type='submit';f.append(label,field,submit);f.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{await setting({kind,action:'rename',name,new_name:field.value});customize()}catch(err){$('#dialogerror').textContent=err.message}finally{submit.disabled=false}};pane.append(f)}));
    row.append(button('Delete',async()=>{if(!confirm(kind==='category'?`Delete ${name}? Its projects will move to Other.`:`Delete ${name} from every card?`))return;try{await setting({kind,action:'delete',name});customize()}catch(err){$('#dialogerror').textContent=err.message}}));
   }section.append(row);
  }body.append(section);
 }
}
function projectMenu(p){const body=open(p.name);body.append(button('Edit project',()=>edit(p)),button('Change icon',()=>iconPicker(p)),button('Delete project',()=>deleteProject(p),'danger'))}
async function deleteProject(p,after){const body=open('Delete '+p.name+'?');body.append(el('p','This permanently deletes the project card, its folder, and every file inside it. This cannot be undone.'));body.append(el('p','Project folder: '+p.folder,'muted'));const actions=el('div',undefined,'formbuttons');const confirm=button('Delete project and files',async()=>{confirm.disabled=true;try{await api('/api/delete-project',{id:p.id,confirm_name:p.name});await refresh();if(after)after();else $('#dialog').close()}catch(e){$('#dialogerror').textContent=e.message}finally{confirm.disabled=false}},'danger');actions.append(button('Cancel',()=>$('#dialog').close()),confirm);body.append(actions)}
async function imageData(file){if(file.size>25000000)throw Error('Choose an image up to 25 MB');const img=new Image(),url=URL.createObjectURL(file);try{img.src=url;await img.decode()}finally{URL.revokeObjectURL(url)}return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(Error('Cannot read image'));r.readAsDataURL(file)})}
async function iconPicker(p){const body=open('Icon · '+p.name),grid=el('div',undefined,'icon-grid');body.append(grid);const choose=async value=>{try{await setting({kind:'icon',id:p.id,value});$('#dialog').close()}catch(e){$('#dialogerror').textContent=e.message}};for(const name of ['D&D','Home','Smart Home','Cars','Audio','Learning','Technology','Music','Travel','Art','Fitness','Work','Nature','Science','Camera','Coffee']){const b=button('',()=>choose(name));b.append(projectIcon(name),el('span',name));b.setAttribute('aria-label',name);grid.append(b)}const file=el('input');file.type='file';file.accept='image/png,image/jpeg,image/webp';file.setAttribute('aria-label','Upload project icon');file.onchange=async()=>{if(!file.files[0])return;file.disabled=true;try{const f=file.files[0];await setting({kind:'icon',action:'upload',id:p.id,name:f.name,data:await imageData(f)});$('#dialog').close()}catch(e){$('#dialogerror').textContent=e.message;file.disabled=false}};body.append(el('h3','Upload an image'),file,button('Use category default',()=>choose(null)));try{const response=await fetch('/api/images?kind=icon');const images=await response.json();if(!response.ok)throw Error('Cannot load icons');for(const item of images){const b=button('',()=>choose(item.url)),img=el('img');img.src=item.url;img.alt=item.name;b.append(img);b.title=item.name;grid.append(b)}}catch(e){$('#dialogerror').textContent=e.message}}
function wallpaper(body){
 const bg=el('section',undefined,'settings-section');bg.append(el('h3','Background image'),el('p','Select a saved background or choose a PNG, JPEG or WebP up to 25 MB. Existing identical images are reused.','muted'));
 const grid=el('div',undefined,'wallpaper-grid');bg.append(grid);fetch('/api/images?kind=background').then(async r=>{if(!r.ok)throw Error('Cannot load backgrounds');return r.json()}).then(images=>{for(const item of images){const b=button('',async()=>{try{await setting({kind:'background',action:'select',name:item.name});workspace.settings()}catch(e){$('#dialogerror').textContent=e.message}}),img=el('img');img.src=item.url;img.alt='';img.loading='lazy';b.append(img,el('span',item.name.replace(/\.[^.]+$/,'')));b.classList.toggle('selected',state.background===item.url);b.setAttribute('aria-label','Use '+item.name);grid.append(b)}}).catch(e=>$('#dialogerror').textContent=e.message);
 const upload=el('input');upload.type='file';upload.accept='image/png,image/jpeg,image/webp';upload.id='background-upload';upload.setAttribute('aria-label','Upload background image');upload.onchange=async()=>{const file=upload.files[0];if(!file)return;upload.disabled=true;try{await setting({kind:'background',action:'upload',name:file.name,data:await imageData(file)});workspace.settings()}catch(err){$('#dialogerror').textContent=err.message}finally{upload.disabled=false}};
 bg.append(upload,button('Reset to hexagons',async()=>{try{await setting({kind:'background',action:'reset'});workspace.settings()}catch(err){$('#dialogerror').textContent=err.message}}));const brightness=el('input');brightness.type='range';brightness.min=0;brightness.max=100;brightness.value=state.brightness;brightness.id='wallpaper-brightness';const bl=el('label','Wallpaper brightness · '+brightness.value+'%');bl.htmlFor=brightness.id;
 brightness.oninput=()=>{bl.textContent='Wallpaper brightness · '+brightness.value+'%';document.body.style.setProperty('--wallpaper-shade',String(1-brightness.value/100))};brightness.onchange=()=>setting({kind:'brightness',value:Number(brightness.value)}).catch(e=>$('#dialogerror').textContent=e.message);bg.append(bl,brightness);body.append(bg);
}

function history(p){const body=open(p.name+' · PDF history');body.append(el('p','Select the master document series. Other PDFs stay available below as supporting documents. Pinning chooses an exact filename.','muted'));
const label=el('label','Master series'),select=el('select');label.htmlFor='series';select.id='series';select.add(new Option('Choose a series…',''));for(const s of p.series)select.add(new Option(s,s));if(p.master_series&&!p.series.includes(p.master_series))select.add(new Option(p.master_series+' (missing)',p.master_series));select.value=p.master_series||'';body.append(label,select);
const act=async changes=>{try{await save(p.id,changes);history(state.projects.find(x=>x.id===p.id))}catch(e){$('#dialogerror').textContent=e.message}};
select.onchange=()=>act({master_series:select.value||null,pin:null});body.append(button('Automatic/latest',()=>act({pin:null})));body.append(el('p',p.pin?'Pinned: '+p.pin:'Mode: Automatic/latest','muted'));for(const w of p.warnings)body.append(el('p',w,'note'));
if(!p.files.length)body.append(el('p','No PDF yet. Copy files into data/Projects/'+p.folder+' and refresh.','muted'));
for(const f of p.files){const row=el('div',undefined,'historyfile'),info=el('div');info.append(documentLink(p,f,f.name),el('small',f.label+' · '+(f.series===p.master_series?'Master series':'Supporting / unselected')+(p.active?.name===f.name?' · CURRENT':'')));if(f.uploaded_at)info.append(el('small','Uploaded '+new Date(f.uploaded_at).toLocaleString()));if(f.note)info.append(el('p',f.note,'version-note'));row.append(info,button(p.pin===f.name?'Pinned':'Pin this',()=>act({pin:f.name})));body.append(row)}
}
$('#back-dashboard').onclick=()=>{location.hash='';};
$('#document-history').onclick=()=>{if(currentDocument)history(state.projects.find(p=>p.id===currentDocument.project.id)||currentDocument.project);};
window.addEventListener('hashchange',route);
$('#close').onclick=()=>$('#dialog').close();$('#dialog').addEventListener('close',()=>$('#dialog').classList.remove('reorder-dialog'));$('#refresh').onclick=()=>refresh(true);for(const id of ['category','status','badge-filter','color-filter'])$('#'+id).onchange=()=>{page=1;render();if($('#search-mode').value==='contents'&&$('#project-search').value.trim())runSearch()};$('#clear-filters').onclick=()=>{for(const id of ['category','status','badge-filter','color-filter'])$('#'+id).value='';$('#project-search').value='';++searchSerial;clearTimeout(searchTimer);clearTimeout(searchPoll);searchResult=null;$('#content-results').replaceChildren();$('#project-search-status').textContent='';page=1;render()};$('#settings').onclick=customize;setInterval(()=>{if(!$('#dialog').open&&!document.hidden&&!currentDocument&&!maps.busy())refresh()},15000);

async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-PACE-Token':state.token},body:JSON.stringify(body)});const result=await r.json();if(!r.ok)throw Error(result.error||'Request failed');return result;}
function matchesSearch(p){const q=$('#project-search').value.trim().toLowerCase();if(!q)return true;if($('#search-mode').value==='contents'&&searchResult)return searchResult.ids.includes(p.id);const text=[p.name,p.summary,p.category,p.status,p.detail,p.priority,p.milestone,p.folder,...p.badges,...p.files.map(f=>f.name)].join(' ').toLowerCase();return q.split(/\s+/).every(t=>text.includes(t));}
async function runSearch(){const serial=++searchSerial,q=$('#project-search').value.trim(),mode=$('#search-mode').value;clearTimeout(searchPoll);searchResult=null;page=1;$('#content-results').replaceChildren();if(!q){$('#project-search-status').textContent='';render();return;}if(mode==='overview'){$('#project-search-status').textContent='Searching card details and PDF filenames';render();return;}
 $('#project-search-status').textContent='Searching PDFs…';
 try{const r=await fetch('/api/search?'+new URLSearchParams({q,mode}));const result=await r.json();if(!r.ok)throw Error(result.error||'Search failed');if(serial!==searchSerial)return;searchResult=result;render();
 const box=$('#content-results');box.replaceChildren();if(result.hits.length)box.append(el('h3','Inside your PDFs'));
 for(const h of result.hits){const p=state.projects.find(p=>p.id===h.id),f=p?.files.find(f=>f.name===h.file);if(!f||($('#category').value&&p.category!==$('#category').value)||($('#status').value&&p.status!==$('#status').value)||($('#badge-filter').value&&!p.badges.includes($('#badge-filter').value))||($('#color-filter').value&&cardColor(p)!==$('#color-filter').value))continue;const row=el('article',undefined,'search-hit');row.append(link(`${p.name} · ${h.file} · Page ${h.page}`,documentRoute(p,f)+'?page='+h.page),el('p',h.excerpt));box.append(row)}
 const ix=result.index;$('#project-search-status').textContent=(ix.running?`Indexing PDFs: ${ix.done}/${ix.total}. Results will refresh…`:`${result.hits.length} PDF page matches${result.hits.length===300?' (first 300)':''}`)+(ix.errors.length?` · ${ix.errors.length} PDFs could not be fully searched`:'');
 if(ix.errors.length){const details=el('details');details.append(el('summary','PDF search limitations'));for(const e of ix.errors)details.append(el('p',e.file+': '+e.message));box.append(details)}
 if(ix.running)searchPoll=setTimeout(runSearch,1800);
 }catch(e){$('#project-search-status').textContent=e.message;}}
$('#project-search').oninput=()=>{++searchSerial;clearTimeout(searchTimer);searchTimer=setTimeout(runSearch,250)};$('#search-mode').onchange=runSearch;
function readBase64(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(Error('Could not read file'));r.readAsDataURL(file)})}
$('#create-project').onclick=()=>{const body=open('Create project'),form=el('form'),name=el('input'),submit=el('button','Create project');name.id='new-project-name';name.placeholder='Project name';name.maxLength=80;name.required=true;submit.type='submit';form.append(el('label','Project and folder name'),name,el('p','Creates a folder on the server alongside your other projects. You can upload the first PDF next.','muted'),submit);body.append(form);form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{const p=await api('/api/create',{name:name.value.trim()});await refresh();uploadDialog(p)}catch(e){$('#dialogerror').textContent=e.message}finally{submit.disabled=false}};};
$('#app-version').onclick=async()=>{const body=open('PACE '+state.version+' · Release notes');try{const r=await fetch('/api/releases');for(const n of await r.json()){const entry=el('details',undefined,'release-entry');entry.append(el('summary',n.name.replace(/\.md$/,'')),el('pre',n.text,'release-text'));body.append(entry)}body.append(el('p','Also available as readable files in data/ReleaseNotes.','muted'))}catch(e){$('#dialogerror').textContent='Could not load release notes'}};
$('#maintenance').onclick=maintenance;
async function maintenance(){const body=open('Backup, restore & updates');try{const r=await fetch('/api/backups');const data=await r.json();if(!r.ok)throw Error(data.error||'Could not load backups');
 const path=el('input');path.id='backup-path';path.value=data.path;const savePath=button('Save backup location',async()=>{try{await setting({kind:'backup',path:path.value});maintenance()}catch(e){$('#dialogerror').textContent=e.message}});
 body.append(el('h3','Backup & restore'),el('p','Backups live outside your PACE installation. This path is on the server; choose another drive for protection against drive failure.','muted'),el('label','Backup folder on server'),path,savePath);
 const mode=el('select');mode.id='backup-mode';mode.add(new Option('Full: app, settings and PDFs','full'));mode.add(new Option('Settings only + app (no project PDFs)','settings'));const status=el('p','','muted');const back=button('Back up now',async()=>{back.disabled=true;status.textContent='Creating and verifying backup…';try{const result=await api('/api/backup',{mode:mode.value});status.textContent='Saved '+result.name;await maintenance()}catch(e){$('#dialogerror').textContent=e.message}finally{back.disabled=false}});body.append(mode,back,status);
 body.append(el('p','Settings-only backups cannot recover deleted PDFs. Restore creates a full safety backup first and preserves this server’s connection settings.','muted'));
 for(const f of data.backups){const row=el('div',undefined,'backup-row');row.append(el('span',f.name+' · '+(f.size/1024/1024).toFixed(1)+' MB'));const download=link('Download','/api/backup-download?'+new URLSearchParams({name:f.name}));download.download=f.name;row.append(download,button('Restore data',async()=>{if(!confirm('Restore saved data from '+f.name+'? Full backups replace the current project collection. A full safety backup will be made first.'))return;try{row.querySelector('button').disabled=true;status.textContent='Restoring…';const result=await api('/api/restore',{name:f.name});await refresh();await maintenance();$('#dialogerror').textContent=result.message}catch(e){$('#dialogerror').textContent=e.message}}));body.append(row)}
 body.append(el('p','If PACE cannot start, use RECOVER_PACE.cmd to recover the app and data from a backup.','muted'));
 body.append(el('h3','Software updates'));const url=el('input');url.id='update-url';url.placeholder='https://…/latest.json';url.value=data.update_url;body.append(el('p','Hosting can be connected later. Only use a release source you trust; updates replace application code.','muted'),el('label','Release manifest URL'),url,button('Save update source',async()=>{try{await setting({kind:'update',url:url.value});maintenance()}catch(e){$('#dialogerror').textContent=e.message}}));
 const output=el('div');const check=button('Check for updates',async()=>{check.disabled=true;try{const result=await api('/api/update-check',{});output.replaceChildren(el('p',result.message));if(result.notes)output.append(el('pre',String(result.notes),'release-text'));if(result.available){const install=button('Back up & install '+result.version,async()=>{if(!confirm('Install '+result.version+'? PACE will back up and restart.'))return;install.disabled=true;try{const r=await api('/api/update-install',{});output.replaceChildren(el('p',r.message),button('Reload dashboard',()=>location.reload()))}catch(e){$('#dialogerror').textContent=e.message;install.disabled=false}});output.append(install)}}catch(e){$('#dialogerror').textContent=e.message}finally{check.disabled=false}});body.append(check,output);
 }catch(e){$('#dialogerror').textContent=e.message}}

function uploadDialog(p){bulkImport(p.id)}
function bulkImport(destination='',initial=[]){
 const body=open(destination?'Import PDFs · '+(state.projects.find(p=>p.id===destination)?.name||'Project'):'Bulk import PDFs'),picker=el('input'),drop=el('div','Drop PDFs here, or choose multiple files.','import-drop'),rows=el('div'),report=el('p','','muted'),submit=button('Import all',run),batch=el('div',undefined,'import-batch');let items=[],running=false;
 picker.type='file';picker.accept='.pdf,application/pdf';picker.multiple=true;picker.id='bulk-pdf-files';
 const targetOptions=select=>{select.add(new Option('Choose destination…',''));for(const p of state.projects)if(!p.missing)select.add(new Option(p.name,p.id));select.add(new Option('New project…','new'));};
 const shared=el('select'),sharedName=el('input');shared.id='bulk-destination';targetOptions(shared);shared.value=destination;sharedName.placeholder='New project name for the batch';sharedName.hidden=true;shared.onchange=()=>sharedName.hidden=shared.value!=='new';
 const assign=button('Assign all',()=>{for(const item of items)if(!item.done){item.target.value=shared.value;item.project.value=sharedName.value;item.project.hidden=shared.value!=='new'}});
 const individual=button('One new project per PDF',()=>{for(const item of items)if(!item.done){item.target.value='new';item.project.hidden=false;item.project.value=item.file.name.replace(/\.pdf$/i,'').slice(0,80)}});
 batch.append(shared,sharedName,assign,individual);body.append(el('p','Review each destination before importing. PDFs are copied to the server; existing filenames are never overwritten. Completed files remain imported if another file fails.','muted'),picker,drop,batch,rows,submit,report);
 function add(files){if(running)return;for(const file of files){if(!file.name.toLowerCase().endsWith('.pdf')){report.textContent='Only PDF files can be imported.';continue}const row=el('div',undefined,'import-row'),target=el('select'),project=el('input'),name=el('input'),note=el('textarea'),result=el('p','','import-result');targetOptions(target);target.value=destination||shared.value;project.placeholder='New project / folder name';project.maxLength=80;project.value=sharedName.value;project.hidden=target.value!=='new';target.onchange=()=>project.hidden=target.value!=='new';name.value=file.name;name.setAttribute('aria-label','PDF filename');target.setAttribute('aria-label','Destination for '+file.name);project.setAttribute('aria-label','New project name for '+file.name);note.placeholder='Version notes (optional)';note.maxLength=4000;note.setAttribute('aria-label','Version notes for '+file.name);const item={file,row,target,project,name,note,result,done:false};row.append(el('strong',file.name+' · '+(file.size/1024/1024).toFixed(1)+' MB'),target,project,name,note,button('Remove',()=>{if(!running){items=items.filter(x=>x!==item);row.remove()}}),result);items.push(item);rows.append(row)}submit.disabled=!items.length;}
 picker.onchange=()=>{add([...picker.files]);picker.value=''};drop.ondragover=e=>{e.preventDefault();drop.classList.add('drop-active')};drop.ondragleave=()=>drop.classList.remove('drop-active');drop.ondrop=e=>{e.preventDefault();e.stopPropagation();drop.classList.remove('drop-active');add([...e.dataTransfer.files])};add(initial);
 const created=new Map();async function run(){if(running)return;$('#dialogerror').textContent='';const todo=items.filter(i=>!i.done);try{if(!todo.length)return;for(const i of todo){if(!i.target.value)throw Error('Choose a destination for every PDF.');if(i.target.value==='new'&&!i.project.value.trim())throw Error('Name each new project.');if(i.file.size>75*1024*1024)throw Error(i.file.name+' is over 75 MB.');if(!i.name.value.toLowerCase().endsWith('.pdf'))throw Error('Each filename must end in .pdf.')} }catch(e){$('#dialogerror').textContent=e.message;return}
 running=true;submit.disabled=true;picker.disabled=true;assign.disabled=true;individual.disabled=true;$('#close').disabled=true;const preventClose=e=>e.preventDefault();$('#dialog').addEventListener('cancel',preventClose);let errors=0;
 for(const i of todo){for(const control of i.row.querySelectorAll('input,select,textarea,button'))control.disabled=true;i.result.textContent='Uploading…';try{let id=i.target.value;if(id==='new'){const name=i.project.value.trim(),key=name.toLowerCase();if(!created.has(key)){const p=await api('/api/create',{name});created.set(key,p.id)}id=created.get(key)}await api('/api/upload',{id,name:i.name.value,data:await readBase64(i.file),note:i.note.value});i.done=true;i.result.textContent='Imported to the server ✓';}catch(e){errors++;i.result.textContent=e.message;for(const control of i.row.querySelectorAll('input,select,textarea,button'))control.disabled=false}}
 await refresh();running=false;$('#close').disabled=false;$('#dialog').removeEventListener('cancel',preventClose);picker.disabled=false;assign.disabled=false;individual.disabled=false;report.textContent=items.filter(i=>i.done).length+' imported'+(errors?' · '+errors+' need attention. Fix the rows and retry.':' · All done.');submit.textContent=errors?'Retry remaining files':'Import all';submit.disabled=!errors;
 }
}
$('#bulk-import').onclick=()=>bulkImport();
$('#dashboard').addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('Files'))e.preventDefault()});
$('#dashboard').addEventListener('drop',e=>{e.preventDefault();if(e.dataTransfer.files.length)bulkImport('',[...e.dataTransfer.files])});
const maps=createMaps({api,setting,setVisual:v=>{state.visual=v},color:cardColor,dialog:open,edit,upload:bulkImport,openProject:p=>{if(p.active)location.hash=documentRoute(p,p.active);else history(p)}});
const workspace=createWorkspace({deleteProject,setHDR,hdrHelp,hdrStatus,getState:()=>state,setting,api,refresh,render,open,el,button,wallpaper,maintenance,releaseNotes:()=>$('#app-version').click(),getPage:()=>page,setPage:n=>{page=n;render()},filters:()=>['category','status','badge-filter','color-filter'].some(id=>$('#'+id).value)||!!$('#project-search').value.trim()});
refresh().then(route);

window.addEventListener('resize',()=>{if(!state)return;const columns=Math.max(1,getComputedStyle($('#cards')).gridTemplateColumns.split(' ').length);for(const b of document.querySelectorAll('.order button[data-project]')){const index=state.projects.findIndex(p=>p.id===b.dataset.project),delta={'←':-1,'→':1,'↑':-columns,'↓':columns}[b.dataset.direction];b.disabled=index+delta<0||index+delta>=state.projects.length}});
