// Bounded local reader closure through the already-proven R10.2 infrastructure.
// No registration, provider, archive or global TaskConfig discovery. High-frequency
// first gaps authorize this narrow exception; semantics stay unassigned.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const repo=path.resolve(__dirname,'../..'),out=path.join(repo,'tmp/audit/r14_real_combat_corpus_20261008_001');
const old=path.join(repo,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const e=require(path.join(old,'exact.cjs'));
e.save=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)+'\n');
e.disasm=(name,rva,end)=>{
 if(end-rva>0x10000)throw Error('LOCAL_READER_SIZE_BOUND');
 const text=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+rva),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
 fs.writeFileSync(path.join(out,name+'.txt'),text);return text;
};
const rt=require(path.join(old,'reader_tools.cjs'));
const receiptPath=path.join(out,'local_reader_receipt.json');
const previous=fs.existsSync(receiptPath)?JSON.parse(fs.readFileSync(receiptPath,'utf8')):{};
const native=previous.native||[];
rt.get=r=>{
 const name='method_'+r.toString(16)+'.txt',archive=path.join(old,name),local=path.join(out,name);
 let text;
 if(fs.existsSync(archive))text=fs.readFileSync(archive,'utf8');
 else if(fs.existsSync(local))text=fs.readFileSync(local,'utf8');
 else {
  if(native.length>=180)throw Error('LOCAL_READER_METHOD_BOUND');
  const end=rt.starts.find(x=>x>r);
  if(!end)throw Error('UNBOUND_LOCAL_READER');
  text=e.disasm(name.slice(0,-4),r,end);
 }
 if(!native.some(x=>x.rva===e.hex(r)))native.push({rva:e.hex(r),method:rt.map.has(r)?e.method(rt.map.get(r)):null,source:fs.existsSync(archive)?path.relative(repo,archive):path.relative(repo,local),sha256:e.sha(Buffer.from(text))});
 return text;
};
const b=require(path.join(old,'structural_decode_core2.cjs'));
const cache=path.join(out,'local_reader_schemas.json');
if(fs.existsSync(cache))for(const s of JSON.parse(fs.readFileSync(cache,'utf8')))b.schemas.set(Number(s.rva),s);
const dispatchCache=path.join(out,'local_reader_dispatch.json');
if(fs.existsSync(dispatchCache))for(const t of JSON.parse(fs.readFileSync(dispatchCache,'utf8')))b.registries.set(Number(t.rva),t.mapping);
// Existing R10.1 root list grammar explains inter-record dictionary keys;
// this is exact framing reuse, never acceptance of an arbitrary trailing string.
const parentSchema=b.schema(0x1eb94850);
e.save('parent_container_schema.json',parentSchema);
const u=require(path.join(old,'usage_map.cjs'));
const rootDispatch=[];
// Exact existing lazy loader jump table -> allocator metadata -> _Resolve ->
// direct FromBinary edge. These directory families occur 181 times in phase 1.
for(const [kind,allocator] of [[2,0x9859880],[3,0x98598d0],[4,0x9859940],[6,0x9859990]]){
 try{
  const table=0xede0bd4,branch=table+e.dll.readInt32LE(e.off(table)+4*kind);
  const owner=u.globalInfo(allocator)?.type_ref?.type;
  if(!owner)throw Error('ROOT_ALLOCATOR_METADATA_GAP');
  const resolve=e.methods(owner.index).find(m=>m.name==='_Resolve');
  const text=rt.get(Number(resolve.rva));
  const calls=[...text.matchAll(/([0-9a-f]+):\s+call\s+0x([0-9a-f]+)/g)].map(x=>({site:e.hex(parseInt(x[1],16)-e.image),rva:parseInt(x[2],16)-e.image}));
  const readers=calls.filter(c=>rt.map.has(c.rva)&&['FromBinary','OJNNBEJLDIJ','MGMEGEDLMAK','DJAPJJBLLJO'].includes(e.method(rt.map.get(c.rva)).name)&&e.method(rt.map.get(c.rva)).parameter_count===2);
  if(readers.length!==1)throw Error('ROOT_DIRECT_READER_GAP');
  const call=readers[0],method=e.method(rt.map.get(call.rva));
  b.schema(call.rva);
  rootDispatch.push({kind,branch:e.hex(branch),allocator:e.hex(allocator),owner,resolve,call,reader:method,source:'R10.2 lazy_ability_directory.txt plus pinned local resolve reader'});
 }catch(err){rootDispatch.push({kind,status:'STRUCTURAL_READER_GAP',question:String(err)});}
}
const batch=JSON.parse(fs.readFileSync(path.join(out,'expanded_decoded_records.json'),'utf8'));
const chars=JSON.parse(fs.readFileSync(path.join(out,'character_records.json'),'utf8'));
const frequencies=new Map();
for(const g of [...batch.record_gaps,...chars.filter(x=>x.status!=='ACCEPTED')]){
 const match=(g.question||'').match(/unproven (?:reader|active bitmap):(0x[\da-f]+)/i);
 if(match)frequencies.set(Number(match[1]),(frequencies.get(Number(match[1]))||0)+1);
}
// High-frequency roots plus the modifier callback reader blocking all referenced
// modifiers. Evidence, attempt frequency and exact locality retained in receipt.
const selected=[...frequencies].filter(([r,n])=>n>=20).sort((a,b)=>b[1]-a[1]).slice(0,14);
const queued=new Set(selected.map(x=>x[0]));queued.add(0x1eb94ee0);
const attempts=[];
if((frequencies.get(0x1e3476a0)||0)>=20){
 // AttackData's two exact native branches are locally reachable from the
 // recovered DamageByAttackProperty reader. ULEB tag 0 -> base, 1 -> subclass.
 const text=rt.get(0x1e3476a0);
 if(!text.includes('cmp    eax,0x1')||!text.includes('jmp    0x19e347b80')||!text.includes('jmp    0x19eb168a0'))throw Error('ATTACK_DATA_DISPATCH_EVIDENCE_MISMATCH');
 b.schemas.set(0x1e3476a0,{rva:'0x1E3476A0',type:'RPG.GameCore.AttackData',kind:'dispatch'});
 b.registries.set(0x1e3476a0,[{method:e.method(rt.map.get(0x1e347b80))},{method:e.method(rt.map.get(0x1eb168a0))}]);
}
for(const r of queued){try{b.schema(r);attempts.push({rva:e.hex(r),frequency:frequencies.get(r)||0,status:'SCHEMA_RECOVERED'});}catch(err){attempts.push({rva:e.hex(r),frequency:frequencies.get(r)||0,status:'STRUCTURAL_READER_GAP',question:String(err)});}}
// Recover dependencies only along concrete reader/list edges. A hard bound keeps
// this from becoming a new whole-game reader archaeology pass.
let progress=true;
while(progress&&b.schemas.size<180){
 progress=false;
 const dependencies=new Set();
 for(const s of b.schemas.values()){
  if(s.kind==='wrapper')dependencies.add(s.child);
  for(const f of s.fields||[])for(const op of f.operations||[]){
   if(op.kind==='reader')dependencies.add(op.rva);
   for(const child of op.children||[])dependencies.add(child);
  }
 }
 for(const r of dependencies){
  if(queued.has(r)||[0x1e14a800,0x1e1487c0,0x1e58a230,0x1e151ae0,0x1e152010,0x1e1534d0].includes(r))continue;
  queued.add(r);progress=true;
  try{b.schema(r);}catch(err){attempts.push({rva:e.hex(r),status:'STRUCTURAL_READER_GAP',question:String(err)});}
  if(b.schemas.size>=180)break;
 }
}
// Predicate dispatch was already proven infrastructure but the R13 cache kept
// only selected bindings. Reuse that exact registry reader, not a new discovery.
try{b.registry(0x1e0ed960);}catch(err){attempts.push({rva:'0x1E0ED960',status:'STRUCTURAL_READER_GAP',question:String(err)});}
e.save('local_reader_schemas.json',[...b.schemas.values()]);
e.save('root_type_dispatch.json',rootDispatch);
e.save('local_reader_dispatch.json',[...b.registries].map(([r,mapping])=>({rva:e.hex(r),mapping})));
e.save('local_reader_receipt.json',{scope:'HIGH_FREQUENCY_LOCAL_CONCRETE_READER_CLOSURE',initial_frequencies:[...(previous.initial_frequencies||[]),...selected.map(([r,n])=>({rva:e.hex(r),frequency:n}))],attempts:[...(previous.attempts||[]),...attempts],native,schema_count:b.schemas.size,method_bound:180,new_provider_archive_registration_discovery:false});
console.log(JSON.stringify({schemas:b.schemas.size,methods:native.length,roots:attempts.slice(0,15)},null,2));
