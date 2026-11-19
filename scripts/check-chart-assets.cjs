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
function verifyThemeECharts() {
 const preview = path.join(root, 'echarts');
 const theme = path.resolve(__dirname, '../django-theme/src/nova_admin/static/nova_admin/vendor/echarts');
 const moduleName = 'echarts.esm.min.js';
 const expected = new Set(fs.readdirSync(preview).filter(name => name !== 'echarts.min.js'));
 expected.add(moduleName);
 const files = fs.readdirSync(theme);
 if (files.length !== expected.size || files.some(name => !expected.has(name))) throw Error('Unexpected theme ECharts inventory');
 for (const name of files) {
  const bytes = fs.readFileSync(path.join(theme, name));
  if (name === moduleName) {
   if (crypto.createHash('sha256').update(bytes).digest('hex') !== '28515f26aa57f87eb1e4ed4eb446927eaf329b5f5e02b4bfd4b0264fea40d1da') throw Error('Theme ECharts module checksum mismatch');
  } else if (!bytes.equals(fs.readFileSync(path.join(preview, name)))) throw Error('Theme ECharts notice mismatch: ' + name);
 }
}
module.exports={verifyChartAssets};
function verifyThemeChartJS() {
 const preview = path.join(root, 'chartjs');
 const theme = path.resolve(__dirname, '../django-theme/src/nova_admin/static/nova_admin/vendor/chartjs');
 const files = fs.readdirSync(preview).sort();
 if (JSON.stringify(fs.readdirSync(theme).sort()) !== JSON.stringify(files)) throw Error('Unexpected theme Chart.js inventory');
 for (const name of files) {
  let expected = fs.readFileSync(path.join(preview, name));
  if (name === 'chart.umd.min.js') {
   // ManifestStaticFilesStorage resolves source maps, which the distribution omits.
   const trailer = Buffer.from('//# sourceMappingURL=chart.umd.min.js.map\n');
   if (!expected.subarray(-trailer.length).equals(trailer)) throw Error('Unexpected Chart.js source map reference');
   expected = expected.subarray(0, -trailer.length);
  }
  if (!fs.readFileSync(path.join(theme, name)).equals(expected)) throw Error('Theme Chart.js asset mismatch: ' + name);
 }
}
if(require.main===module){try{verifyThemeECharts();verifyThemeChartJS();console.log(JSON.stringify(verifyChartAssets()));}catch(error){console.error(error.message);process.exitCode=1;}}
