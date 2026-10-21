// Narrow exact-build reader extension, only RVAs in reachable dependency gaps.
// Reuses frozen R10.2 extraction; all writes are confined to the R16 audit.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const repo=path.resolve(__dirname,'../..'),out=path.join(repo,'tmp/audit/r16_ability_dependency_closure_20261008_001');
const old=path.join(repo,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const r14=path.join(repo,'tmp/audit/r14_real_combat_corpus_20261008_001');
const e=require(path.join(old,'exact.cjs'));
e.save=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)+'\n');
const receiptPath=path.join(out,'local_reader_receipt.json');
const receipt=fs.existsSync(receiptPath)?JSON.parse(fs.readFileSync(receiptPath,'utf8')):{native:[],attempts:[]};
const bound=180;
const rt=require(path.join(old,'reader_tools.cjs'));
rt.get=r=>{
 if(rt.map.has(r)&&e.method(rt.map.get(r)).name==='.cctor')throw Error('NEW_REGISTRY_EXTRACTION_OUT_OF_SCOPE');
 const name='method_'+r.toString(16)+'.txt';
 const cached=[path.join(old,name),path.join(r14,name),path.join(out,name)].find(p=>fs.existsSync(p));
 let text,source=cached;
 if(cached)text=fs.readFileSync(cached,'utf8');
 else {
  if(receipt.native.length>=bound)throw Error('R16_METHOD_BUDGET');
  const end=rt.starts.find(x=>x>r);
  if(!end||end-r>0x10000)throw Error('R16_METHOD_SIZE_BOUND');
  text=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),
    '--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
  source=path.join(out,name);fs.writeFileSync(source,text);
 }
 if(!receipt.native.some(x=>x.rva===e.hex(r)))receipt.native.push({rva:e.hex(r),
  method:rt.map.has(r)?e.method(rt.map.get(r)):null,source:path.relative(repo,source),sha256:e.sha(Buffer.from(text))});
 return text;
};
// Avoid registry/provider discovery: dispatch maps were already proven in R14.
const b=require(path.join(old,'structural_decode_core2.cjs'));
for(const s of JSON.parse(fs.readFileSync(path.join(r14,'local_reader_schemas.json'),'utf8')))b.schemas.set(Number(s.rva),s);
for(const t of JSON.parse(fs.readFileSync(path.join(r14,'local_reader_dispatch.json'),'utf8')))b.registries.set(Number(t.rva),t.mapping);
// R14's validated archive-derived dispatch map also contains proven local leaf
// dispatchers. Seed them directly rather than reopening their registry cctors.
for(const [r,mapping] of Object.entries(JSON.parse(fs.readFileSync(path.join(r14,'reader_dispatch.json'),'utf8')))){
 if(b.registries.has(Number(r)))continue;
 const table=[];for(const [ordinal,reader] of Object.entries(mapping))table[Number(ordinal)]={method:{rva:reader}};
 b.registries.set(Number(r),table);
}
const provenRegistries=new Set(b.registries.keys());
const local=path.join(out,'local_reader_schemas.json');
if(fs.existsSync(local))for(const s of JSON.parse(fs.readFileSync(local,'utf8')))b.schemas.set(Number(s.rva),s);
const selected=JSON.parse(fs.readFileSync(path.join(out,'selected_reader_requests.json'),'utf8'));
for(const request of selected){
 const r=Number(request.rva);
 if(receipt.attempts.some(x=>Number(x.rva)===r&&!String(x.question).includes('R16_METHOD_BUDGET')))continue;
 try {
  const s=b.schema(r);
  if(s.kind==='dispatch'&&!provenRegistries.has(r))throw Error('NEW_DISPATCH_DISCOVERY_OUT_OF_SCOPE');
  // Exact integer masks must remain representable. Reject JS rounding.
  for(const f of s.fields||[])if(typeof f.mask==='number'&&!Number.isSafeInteger(f.mask)){
   const text=rt.get(r),call=(f.callsite||[])[0];
   const lines=text.split('\n');let at=call?lines.findIndex(l=>l.includes((e.image+Number(call)).toString(16))):lines.length;
   let tests=lines.slice(0,at).filter(l=>/test\s+(?:[a-z0-9]+),0x/.test(l));
   const match=tests.at(-1)?.match(/test\s+r14\w*,0x([0-9a-f]+)/);
   if(!match)throw Error('EXACT_HIGH_MASK_EVIDENCE_MISSING');
   const mask=BigInt('0x'+match[1])<<64n;
   if(mask===0n||(mask&(mask-1n)))throw Error('EXACT_HIGH_MASK_NOT_ONE_HOT');
   f.mask=mask.toString();
  }
  receipt.attempts.push({...request,status:'SCHEMA_RECOVERED',type:s.type});
 }catch(err){receipt.attempts.push({...request,status:'STRUCTURAL_READER_GAP',question:String(err)});b.schemas.delete(r);}
}
const initial=new Set(JSON.parse(fs.readFileSync(path.join(r14,'local_reader_schemas.json'),'utf8')).map(s=>Number(s.rva)));
e.save('local_reader_schemas.json',[...b.schemas.values()].filter(s=>!initial.has(Number(s.rva))));
e.save('local_reader_receipt.json',{...receipt,method_bound:bound,scope:'ONLY_CONCRETE_REACHABLE_REFERENCE_GAPS',
 new_provider_archive_registration_discovery:false});
console.log(JSON.stringify({new_schemas:[...b.schemas.keys()].filter(r=>!initial.has(r)).length,methods:receipt.native.length,attempts:receipt.attempts.length}));
