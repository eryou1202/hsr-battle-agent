// Bounded 4.6.51 methods only. Reuse trusted R09 mapping and pinned R10.2 source.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const repo=path.resolve(__dirname,'../..'),old=path.join(repo,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const e=require(path.join(old,'exact.cjs'));
const out=path.join(repo,'tmp/audit/r19_damage_continuation_20261010_001');
const map=new Map();for(let i=0;i<772632;i++){const r=Number(e.dll.readBigUInt64LE(e.pt+i*8))-e.image;if(r>0&&!map.has(r))map.set(r,i);}
const starts=[...map.keys()].sort((a,b)=>a-b);
function describe(r,disassemble=false){
 const m=map.has(r)?e.method(map.get(r)):null;
 if(!disassemble)return m;
 const end=starts.find(x=>x>r);if(!end||end-r>0x10000)throw Error('BOUNDED_METHOD_ONLY');
 const text=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
 const name='native_'+r.toString(16)+'.txt';fs.writeFileSync(path.join(out,name),text);
 return {method:m,end:e.hex(end),disassembly:name,sha256:e.sha(Buffer.from(text)),calls:[...text.matchAll(/([0-9a-f]+):\s+(call|jmp)\s+0x([0-9a-f]+)/g)].map(x=>({site:e.hex(parseInt(x[1],16)-e.image),target:e.hex(parseInt(x[3],16)-e.image),method:describe(parseInt(x[3],16)-e.image)}))};
}
const args=process.argv.slice(2);
if(args[0]==='opcode'){
 const base=0x1e197720;
 const result=[0,1,2,4,17].map(op=>({opcode:op,table_rva:e.hex(base+op*4),signed_relative:e.dll.readInt32LE(e.off(base+op*4)),branch:e.hex(base+e.dll.readInt32LE(e.off(base+op*4)))}));
 fs.writeFileSync(path.join(out,'opcode_table.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
}else if(args[0]==='inventory'){
 const result=[0x1e5265c0,0x1e468660,0x1e196300,0xf0ea100].map(r=>{const m=describe(r);return {method:m,type:e.type(m.type_index),fields:e.fields(m.type_index),methods:e.methods(m.type_index)};});
 fs.writeFileSync(path.join(out,'native_inventory.json'),JSON.stringify({source_pin:e.pin,source_files:e.manifest.files.filter(f=>['GameAssembly.dll','StarRail_Data/il2cpp_data/Metadata/global-metadata.dat'].includes(f.relative_path)),result},null,2)+'\n');
 console.log(JSON.stringify(result.map(x=>({type:x.type,methods:x.methods})),null,2));
}else{
 if(args.length>20)throw Error('METHOD_BUDGET');
 const result=args.map(x=>describe(Number(x),true));
 fs.writeFileSync(path.join(out,'native_calls_'+args.map(x=>Number(x).toString(16)).join('_')+'.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result.map(x=>({method:x.method,disassembly:x.disassembly,calls:x.calls.filter(c=>c.method).map(c=>({site:c.site,target:c.target,name:c.method.type+'.'+c.method.name}))})),null,2));
}
