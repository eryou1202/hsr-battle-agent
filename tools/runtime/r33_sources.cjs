// Exact offline constructor edges only. No process access or archive search.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'tmp/audit/r33_modifier_instance_authority_20261109_001/native');fs.mkdirSync(out,{recursive:true});
const base=path.join(root,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const e=require(path.join(base,'exact.cjs')),rt=require(path.join(base,'reader_tools.cjs'));
const rows=[];
for(const r of [0xB75A130,0xEEA2780]){
 const end=rt.starts.find(x=>x>r);if(!rt.map.has(r)||!end||end-r>0x10000)throw Error('bounds');
 const artifact='method_'+r.toString(16)+'.txt';
 const tx=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
 fs.writeFileSync(path.join(out,artifact),tx);const method=e.method(rt.map.get(r));
 rows.push({rva:e.hex(r),end:e.hex(end),method,artifact,sha256:e.sha(Buffer.from(tx)),type:e.type(method.type_index),fields:e.fields(method.type_index)});
}
fs.writeFileSync(path.join(out,'additional_methods.json'),JSON.stringify({source_version:'4.6.51',manifest_sha256:e.pin,additional_bodies:2,limit:12,hops_per_blocker:1,methods:rows},null,2)+'\n');
console.log(rows.map(x=>({rva:x.rva,method:x.method,fields:x.fields})));
