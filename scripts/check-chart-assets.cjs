#!/usr/bin/env node
// Verify the unchanged, pinned upstream chart distributions without network access.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../dist/vendor/charts');
function verifyChartAssets(directory=root){
 const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
 if(manifest.schema!==1)throw Error('Unsupported chart manifest');
 const ids=new Set(),seen=new Set();
 for(const item of manifest.libraries){
  if(ids.has(item.id))throw Error('Duplicate chart dependency');ids.add(item.id);
  if(!item.archive.url.startsWith('https://registry.npmjs.org/')||!/^sha512-/.test(item.archive.integrity))throw Error('Unpinned chart source');
  for(const file of item.files){
   const target=path.resolve(directory,file.path);if(!target.startsWith(path.resolve(directory)+path.sep)||seen.has(file.path))throw Error('Invalid chart asset path');seen.add(file.path);
   const bytes=fs.readFileSync(target);if(bytes.length!==file.bytes||crypto.createHash('sha256').update(bytes).digest('hex')!==file.sha256)throw Error('Chart asset differs from upstream: '+file.path);
  }
 }
 const actual=new Set();
 function collect(folder){for(const entry of fs.readdirSync(folder,{withFileTypes:true})){const target=path.join(folder,entry.name);if(entry.isSymbolicLink())throw Error('Symlink in chart bundle');if(entry.isDirectory())collect(target);else actual.add(path.relative(directory,target).split(path.sep).join('/'));}}
 collect(directory);actual.delete('manifest.json');if(actual.size!==seen.size||[...actual].some(name=>!seen.has(name)))throw Error('Unrecorded chart asset');
 for(const required of ['echarts','chartjs','uplot','color','zrender','tslib'])if(!ids.has(required))throw Error('Missing chart runtime or license: '+required);
 return {status:'passed',chartLibraries:3,upstreamPackages:ids.size,files:seen.size};
}
module.exports={verifyChartAssets};
if(require.main===module){try{console.log(JSON.stringify(verifyChartAssets()));}catch(error){console.error(error.message);process.exitCode=1;}}
