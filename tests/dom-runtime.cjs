const {JSDOM}=require('jsdom');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
async function createApp(options={}){
 const base=path.join(__dirname,'../dist');
 const html=fs.readFileSync(path.join(base,'index.html'),'utf8').replace(/<script[\s\S]*?<\/script>/g,'');
 const dom=new JSDOM(html,{url:options.url||'https://example.test/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window;if(options.platform!==undefined)Object.defineProperty(w.navigator,'platform',{configurable:true,value:options.platform});w.structuredClone=structuredClone;w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=function(){};
 for(const [key,value] of Object.entries(options.storage||{}))w.localStorage.setItem(key,value);
 let mediaListener;const media={matches:!!options.systemDark,addEventListener(name,listener){if(name==='change')mediaListener=listener;}};
 w.matchMedia=()=>media;
 options.beforeLoad?.(w);
 const context=dom.getInternalVMContext(),modules=new Map();
 // Let the VM link the complete graph, including shared transitive dependencies.
 function load(file){if(modules.has(file))return modules.get(file);const m=new vm.SourceTextModule(fs.readFileSync(file,'utf8'),{context,identifier:file});modules.set(file,m);return m;}
 const entry=load(path.join(base,'js/app.js'));await entry.link((spec,parent)=>load(path.resolve(path.dirname(parent.identifier),spec)));await entry.evaluate();
 return {dom,w,d:w.document,setSystemDark(value){media.matches=value;mediaListener?.({matches:value});},close:()=>w.close()};
}
module.exports={createApp};
