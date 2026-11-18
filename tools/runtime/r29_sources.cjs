// Bounded, offline same-build executor investigation. Never attaches to a process.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const repo=path.resolve(__dirname,'../..'),out=path.join(repo,'tmp/audit/r29_original_executor_context_20261108_001');
fs.mkdirSync(out,{recursive:true});
const old=path.join(repo,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const e=require(path.join(old,'exact.cjs'));
const save=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2)+'\n');
const names=/SetDynamicValueBy(Property|CharacterCount)|FireProjectile|SetTeamFormation|ByDistance|ChoseSequencedSkillAxis|UseSequencedSkill|AddModifier|DamageByAttackProperty/;
if(process.argv[2]==='globals'){
 const u=require(path.join(old,'usage_map.cjs'));
 const rows=process.argv.slice(3).map(x=>{const r=Number(x),g=u.globalInfo(r);return {rva:e.hex(r),binding:g,...(g?.tag===6?{generic:u.generic(g.index)}:{})};});save('selected_global_bindings.json',rows);console.log(JSON.stringify(rows));
}else if(process.argv[2]==='types'){
 const p=path.join(out,'selected_executor_types.json'),prior=fs.existsSync(p)?JSON.parse(fs.readFileSync(p)):[];
 const rows=process.argv.slice(3).map(x=>{const i=Number(x);return {type:e.type(i),fields:e.fields(i),methods:e.methods(i)};});save('selected_executor_types.json',[...prior.filter(x=>!rows.some(y=>y.type.index===x.type.index)),...rows]);console.log(JSON.stringify(rows));
}else if(process.argv[2]==='xrefs'){
 const u=require(path.join(old,'usage_map.cjs')),targets=new Set([23477,23479,23462,22967,21088]);
 const globals=new Map(),rows=[];
 for(let i=0;i<u.range(328749);i++){const p=u.pair(i);if(p.tag!==1)continue;const t=e.typeRef(p.index);if(targets.has(t?.data)&&[17,18].includes(t?.kind)&&p.global_rva)globals.set(Number(p.global_rva),{usage:p,type:t});}
 for(const s of e.sections.filter(s=>s.name==='il2cpp'))for(let p=s.raw;p<s.raw+s.raw_size-7;p++){
  if((e.dll[p]===0x48||e.dll[p]===0x4c)&&e.dll[p+1]===0x8b&&(e.dll[p+2]&0xc7)===5){
   const site=s.rva+p-s.raw,target=site+7+e.dll.readInt32LE(p+3);if(globals.has(target))rows.push({site:e.hex(site),...globals.get(target)});
  }
 }
 const rt=require(path.join(old,'reader_tools.cjs'));
 for(const row of rows){const site=Number(row.site);let lo=0,hi=rt.starts.length;while(lo<hi){const mid=(lo+hi)>>1;if(rt.starts[mid]<=site)lo=mid+1;else hi=mid;}row.enclosing=e.method(rt.map.get(rt.starts[lo-1]));}
 save('config_type_load_xrefs.json',{manifest_sha256:e.pin,globals:[...globals.values()],rows});console.log(JSON.stringify(rows.map(x=>({site:x.site,config:x.type.type.name,enclosing:x.enclosing}))));
}else if(process.argv[2]==='methods'){
 const rows=[];for(let i=0;i<772632;i++){const m=e.method(i);if(names.test(m.name))rows.push(m);}
 save('named_method_references.json',{manifest_sha256:e.pin,rows});console.log(JSON.stringify(rows));
}else if(process.argv[2]==='generics'){
 const u=require(path.join(old,'usage_map.cjs')),targets=new Set([23477,23479,23462,22967,21088]);
 const rows=[],seen=new Set();for(let i=0;i<u.range(328749);i++){
  const p=u.pair(i);if(p.tag!==6||seen.has(p.index))continue;seen.add(p.index);
  const g=u.generic(p.index);
  if([...(g.class_args||[]),...(g.method_args||[])].some(a=>targets.has(a.data)&&[17,18].includes(a.kind)))rows.push({usage:p,generic:g});
 }
 save('executor_generic_references.json',{manifest_sha256:e.pin,rows});console.log(JSON.stringify(rows));
}else if(process.argv[2]==='bindings'){
 const targets=new Set([23477,23479,23462,22982,22967,23308,21088,15661,22818]);
 const rows=[];for(let i=0;i<84936;i++){
  const fields=e.fields(i).filter(f=>targets.has(f.type?.data)&&[17,18].includes(f.type?.kind));
  if(fields.length)rows.push({type:e.type(i),fields,methods:e.methods(i)});
 }
 save('executor_config_references.json',{manifest_sha256:e.pin,targets:[...targets],rows});
 console.log(JSON.stringify(rows));
}else if(process.argv[2]==='inventory'){
 const rows=[];for(let i=0;i<84936;i++){const t=e.type(i);if(names.test(t.name))rows.push({type:t,fields:e.fields(i),methods:e.methods(i)});}
 save('executor_types.json',{manifest_sha256:e.pin,rows});
 console.log(rows.map(x=>({type:x.type.name,index:x.type.index,methods:x.methods.map(m=>({name:m.name,rva:m.rva}))})));
}else{
 const rt=require(path.join(old,'reader_tools.cjs'));
 const receiptPath=path.join(out,'native_methods.json');
 const receipt=fs.existsSync(receiptPath)?JSON.parse(fs.readFileSync(receiptPath)): {manifest_sha256:e.pin,limit:40,methods:[]};
 for(const arg of process.argv.slice(2)){
  const r=Number(arg);if(receipt.methods.some(x=>x.rva===e.hex(r)))continue;
  if(receipt.methods.length>=40)throw Error('40_METHOD_BOUND');
  const end=rt.starts.find(x=>x>r);if(!rt.map.has(r)||!end||end-r>0x10000)throw Error('EXACT_METHOD_BOUND');
  const tx=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
  const artifact='method_'+r.toString(16)+'.txt';fs.writeFileSync(path.join(out,artifact),tx);
  const calls=[...tx.matchAll(/([0-9a-f]+):\s+(call|jmp)\s+0x([0-9a-f]+)/g)].map(x=>{const target=parseInt(x[3],16)-e.image;return {site:e.hex(parseInt(x[1],16)-e.image),target:e.hex(target),method:rt.map.has(target)?e.method(rt.map.get(target)):null};});
  const row={rva:e.hex(r),end:e.hex(end),method:e.method(rt.map.get(r)),sha256:e.sha(Buffer.from(tx)),artifact,calls};receipt.methods.push(row);save('native_methods.json',receipt);console.log(JSON.stringify(row));
 }
 save('native_methods.json',receipt);
}
