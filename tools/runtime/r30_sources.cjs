// Selected metadata reconciliation only; reuses R29 bodies without reacquisition.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..'),old=path.join(root,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const e=require(path.join(old,'exact.cjs')),u=require(path.join(old,'usage_map.cjs'));
const out=path.join(root,'tmp/audit/r30_dynamic_context_closure_20261108_001');
fs.mkdirSync(out,{recursive:true});
const globals=[0x9804fa0,0x985cf68,0x98ec078,0x990d498,0x98ec060,0x98f3568,0x98f6818,0x99ddee8,0x99dded0,0x99ddf30].map(r=>{const binding=u.globalInfo(r);return {rva:e.hex(r),binding,...(binding?.tag===6?{generic:u.generic(binding.index)}:{})};});
const indices=new Set([55845,9948,56913,...globals.map(g=>g.binding?.type_ref?.data).filter(i=>Number.isInteger(i)&&i>=0&&i<84936)]);
const native=JSON.parse(fs.readFileSync(path.join(root,'tmp/audit/r29_original_executor_context_20261108_001/native_methods.json')));
for(const r of native.methods.filter(m=>['0x1DCA0FD0','0x127100D0','0x163ECB70'].includes(m.rva)))indices.add(r.method.type_index);
for(const g of globals)for(const t of [...(g.generic?.class_args||[]),...(g.generic?.method_args||[])])if([17,18].includes(t.kind))indices.add(t.data);
const types=[...indices].map(i=>({type:e.type(i),fields:e.fields(i),methods:e.methods(i)}));
const scope_tables=[{base:0xedf7c94,scopes:[1,2,3,4,5,6,7,8]},{base:0xedf7cb4,scopes:[0,1,2,3,4,5,6,7,8]}].map(t=>({base:e.hex(t.base),entries:t.scopes.map((scope,i)=>({scope,target:e.hex(t.base+e.dll.readInt32LE(e.off(t.base)+i*4))}))}));
fs.writeFileSync(path.join(out,'selected_metadata.json'),JSON.stringify({manifest_sha256:e.pin,new_method_bodies:0,globals,types,scope_tables},null,2)+'\n');
console.log(JSON.stringify({types:types.map(t=>({index:t.type.index,name:t.type.name,methods:t.methods.length})),new_method_bodies:0}));
if(process.argv[2]==='bounded'){
 if(fs.existsSync(path.join(out,'native_methods.json')))throw Error('R30_BODIES_ALREADY_CAPTURED_REUSE_REQUIRED');
 const rt=require(path.join(old,'reader_tools.cjs')),cp=require('child_process');
 const requests=[{rva:0x1ec22590,blocker:'writer range conversion',hop:1,hypothesis:'identify operation before set_Val; independent raw numeric contract'}, {rva:0xf0ea840,blocker:'scope-0 fallback context identity',hop:1,hypothesis:'identify concrete owner returned before +0x18 store lookup'}, {rva:0xb904bf0,blocker:'candidate predicate status ownership',hop:1,hypothesis:'distinguish task status dispatch from generic truth'}];
 const methods=requests.map(req=>{const r=req.rva,end=rt.starts.find(x=>x>r);if(native.methods.some(x=>Number(x.rva)===r))throw Error('REACQUISITION_FORBIDDEN');if(!rt.map.has(r)||end-r>0x10000)throw Error('BOUND');const tx=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});const artifact='method_'+r.toString(16)+'.txt';fs.writeFileSync(path.join(out,artifact),tx);return {...req,rva:e.hex(r),end:e.hex(end),method:e.method(rt.map.get(r)),artifact,sha256:e.sha(Buffer.from(tx))};});
 fs.writeFileSync(path.join(out,'native_methods.json'),JSON.stringify({methods,limit:12,paths:['dynamic scope ownership','keyed writer and numeric/status contract'],max_hops:1},null,2)+'\n');console.log(JSON.stringify(methods));
}
