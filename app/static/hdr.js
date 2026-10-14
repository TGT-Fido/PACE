/* Real extended-range WebGPU highlights. HTML, PDFs and SDR uploads stay SDR. */
export const hdrHelp='Legacy is the default renderer. HDR adds extended-range highlights to project accents, icons and map nodes without changing the theme palette. In v7 it is available only on the host PC at localhost or 127.0.0.1. Use an HDR-capable browser/display with Windows HDR enabled. LAN and Tailscale URLs use Legacy; remote HTTPS HDR is deferred. HDR does not convert uploaded SDR wallpapers or PDFs into HDR. If initialization fails, Legacy remains visible.';
let mode='legacy',canvas,device,context,texture,pipeline,sampler,mask,ctx,observer,serial=0,frame=0,message='Legacy rendering',ready=false;
export function hdrStatus(){return message}
function status(text){message=text;const node=document.getElementById('hdr-status');if(node)node.textContent=text}
function stop(){ready=false;observer?.disconnect();observer=null;cancelAnimationFrame(frame);frame=0;texture?.destroy();texture=null;context?.unconfigure();context=null;canvas?.remove();canvas=null;device?.destroy();device=null}
function schedule(){if(!ready||frame)return;frame=requestAnimationFrame(()=>{frame=0;draw()})}
function draw(){if(!ready||!canvas||document.hidden)return;try{
 const ratio=Math.min(devicePixelRatio||1,2),w=Math.max(1,Math.floor(innerWidth*ratio)),h=Math.max(1,Math.floor(innerHeight*ratio));
 if(mask.width!==w||mask.height!==h){canvas.width=mask.width=w;canvas.height=mask.height=h;texture?.destroy();texture=device.createTexture({size:[w,h],format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.COPY_DST|GPUTextureUsage.RENDER_ATTACHMENT})}
 ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,innerWidth,innerHeight);
 if(!document.querySelector('dialog[open]')&&!document.body.classList.contains('reading')){
 for(const item of document.querySelectorAll('.card,.map-node,.brand .logo')){
  const r=item.getBoundingClientRect();if(!r.width||r.bottom<0||r.top>innerHeight)continue;
  const style=getComputedStyle(item);const color=style.getPropertyValue('--accent').trim()||style.getPropertyValue('--node-color').trim()||'#b398ff';
  ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.shadowColor=color;ctx.shadowBlur=5;
  ctx.beginPath();if(item.classList.contains('card')){ctx.moveTo(r.left+14,r.top+2);ctx.lineTo(r.right-14,r.top+2)}else if(item.classList.contains('map-node')){ctx.roundRect(r.left+1,r.top+1,r.width-2,r.height-2,Math.min(18,r.height/2))}else{ctx.moveTo(r.left+8,r.bottom-2);ctx.lineTo(r.right-8,r.bottom-2)}ctx.stroke();
 }}
 device.queue.copyExternalImageToTexture({source:mask},{texture,premultipliedAlpha:false},[w,h]);
 const group=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:sampler},{binding:1,resource:texture.createView()}]});
 const encoder=device.createCommandEncoder(),pass=encoder.beginRenderPass({colorAttachments:[{view:context.getCurrentTexture().createView(),clearValue:[0,0,0,0],loadOp:'clear',storeOp:'store'}]});pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.draw(3);pass.end();device.queue.submit([encoder.finish()]);
 }catch(e){stop();status('Legacy active — HDR rendering failed: '+e.message)}}
export async function setHDR(value){if(value===mode)return;mode=value;const request=++serial;stop();if(mode!=='hdr'){status('Legacy rendering');return}
 if(!['localhost','127.0.0.1','[::1]'].includes(location.hostname)){status('Legacy active — v7 HDR is available on the host computer only.');return}
 if(!isSecureContext||!navigator.gpu){status('Legacy active — this browser does not expose WebGPU.');return}
 status('Initializing HDR…');try{
 const adapter=await navigator.gpu.requestAdapter();if(!adapter)throw Error('No compatible GPU adapter');const next=await adapter.requestDevice();if(request!==serial){next.destroy();return}device=next;
 canvas=document.createElement('canvas');canvas.id='hdr-layer';canvas.setAttribute('aria-hidden','true');document.body.append(canvas);context=canvas.getContext('webgpu');if(!context)throw Error('No WebGPU canvas');context.configure({device,format:'rgba16float',alphaMode:'premultiplied',colorSpace:'srgb',toneMapping:{mode:'extended'}});
 if(context.getConfiguration?.().toneMapping?.mode!=='extended')throw Error('Extended tone mapping is not supported');
 device.pushErrorScope('validation');
 const shader=device.createShaderModule({code:`@group(0) @binding(0) var samp: sampler; @group(0) @binding(1) var tex: texture_2d<f32>;
 struct Out { @builtin(position) p:vec4f, @location(0) uv:vec2f }
 @vertex fn vs(@builtin(vertex_index) i:u32)->Out { var p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3)); var o:Out;o.p=vec4f(p[i],0,1);o.uv=vec2f((p[i].x+1)*0.5,1-(p[i].y+1)*0.5);return o; }
 @fragment fn fs(o:Out)->@location(0) vec4f { let c=textureSample(tex,samp,o.uv); return vec4f(c.rgb*2.5*c.a,c.a); }`});
 const activeDevice=device;const nextPipeline=await activeDevice.createRenderPipelineAsync({layout:'auto',vertex:{module:shader,entryPoint:'vs'},fragment:{module:shader,entryPoint:'fs',targets:[{format:'rgba16float'}]},primitive:{topology:'triangle-list'}});const validation=await activeDevice.popErrorScope();if(validation)throw Error(validation.message);if(request!==serial)return;pipeline=nextPipeline;
 sampler=device.createSampler({magFilter:'linear',minFilter:'linear'});mask=document.createElement('canvas');mask.width=0;mask.height=0;ctx=mask.getContext('2d');ready=true;
 observer=new MutationObserver(schedule);observer.observe(document.querySelector('#dashboard'),{subtree:true,childList:true,attributes:true});observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 device.lost.then(info=>{if(request===serial&&mode==='hdr'){stop();status('Legacy active — GPU connection lost. Switch Legacy then HDR to retry.')}});
 status(matchMedia('(dynamic-range: high)').matches?'HDR highlight renderer active — verify brightness on your HDR display.':'HDR renderer initialized; browser reports an SDR display.');schedule();
 }catch(e){if(request===serial){stop();status('Legacy active — '+e.message)}}}
window.addEventListener('resize',schedule);window.addEventListener('scroll',schedule,true);document.addEventListener('visibilitychange',schedule);document.addEventListener('pace-layout',schedule);document.addEventListener('click',schedule);
