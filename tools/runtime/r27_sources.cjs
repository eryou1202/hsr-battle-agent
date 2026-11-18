// Targeted pinned native schema recovery. No process attachment or game execution.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const repo=path.resolve(__dirname,'../..'),out=path.join(repo,'tmp/audit/r27_real_character_monster_20261022_001');
const old=path.join(repo,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const r14=path.join(repo,'tmp/audit/r14_real_combat_corpus_20261008_001');
const r16=path.join(repo,'tmp/audit/r16_ability_dependency_closure_20261008_001');
const e=require(path.join(old,'exact.cjs'));
e.save=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)+'\n');
e.disasm=(name,rva,end)=>{
 if(end-rva>0x1000)throw Error('EXPLICIT_SPAN_BOUND');
 const text=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+rva),
  '--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
 fs.writeFileSync(path.join(out,name+'.txt'),text);return text;
};
const rt=require(path.join(old,'reader_tools.cjs'));
const receiptPath=path.join(out,'native_reader_receipt.json');
const receipt=fs.existsSync(receiptPath)?JSON.parse(fs.readFileSync(receiptPath,'utf8')):{methods:[],attempts:[]};
rt.get=r=>{
 if(rt.map.has(r)&&e.method(rt.map.get(r)).name==='.cctor')throw Error('NEW_REGISTRY_OUT_OF_SCOPE');
 const name='method_'+r.toString(16)+'.txt';
 let p=[old,r14,r16,out].map(d=>path.join(d,name)).find(p=>fs.existsSync(p)),text;
 if(p)text=fs.readFileSync(p,'utf8');
 else {
  if(receipt.methods.length>=100)throw Error('R27_100_METHOD_BOUND');
  const end=rt.starts.find(x=>x>r);
  if(!end||end-r>0x10000)throw Error('METHOD_SPAN_BOUND');
  text=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),
   '--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
  p=path.join(out,name);fs.writeFileSync(p,text);
 }
 if(!receipt.methods.some(x=>Number(x.rva)===r))receipt.methods.push({rva:e.hex(r),method:rt.map.has(r)?e.method(rt.map.get(r)):null,
  artifact:path.relative(repo,p).replaceAll('\\','/'),sha256:e.sha(Buffer.from(text))});
 return text;
};
// Keep the inherited extractor immutable. Recognize exact additional native
// generic call forms in an isolated module; descriptors still prove each type.
const Module=require('module');
let core=fs.readFileSync(path.join(old,'structural_decode_core2.cjs'),'utf8');
core=core.replaceAll('bl|bh|bx|ebx|rbx|sil|esi|rsi|r12b|r12d|r12|r14b|r14d|r14',
 'al|ah|ax|eax|rax|bl|bh|bx|ebx|rbx|sil|esi|rsi|r12b|r12d|r12|r14b|r14d|r14');
core=core.replace('[0x17b6b7f0,0x17b71040,0x17b9bcc0,0x17b9c0b0]',
 '[0x17b6a520,0x17b6a790,0x17b6bb90,0x17b6b560,0x17b6b7f0,0x17b71040,0x17b9bcc0,0x17b9c0b0,0x17b9c460]');
core=core.replace("if(calls.some(x=>x.rva===0x1cf522d0))",`if(calls.some(x=>x.rva===0x17b6b560)){
 const g=globals.find(x=>x.tag===6);if(!g)throw Error('enum array descriptor missing');
 const generic=u.generic(g.index),arg=generic.class_args?.[0]??generic.method_args?.[0];
 const underlying=e.fields(arg.data).find(x=>x.name==='value__');
 if(generic.method.index!==74516||!underlying)throw Error('unproved enum element reader');
 f.operations=[{kind:'enum_list',element:{kind:'enum',type:arg.type,underlying:underlying.type.kind},generic,bindings:globals.filter(x=>x.tag===6)}];
 }else if(calls.some(x=>[0x17b6a520,0x17b6a790,0x17b6bb90].includes(x.rva))){
 const gs=globals.filter(x=>x.tag===3||x.tag===6);
 if(gs.length!==1)throw Error('struct array element descriptor count');
 let m=gs[0].method;if(gs[0].tag===6)m=u.generic(gs[0].index).method;
 if(!m?.rva)throw Error('struct array instantiated element missing');
 f.operations=[{kind:'list',children:[Number(m.rva)],bindings:gs}];
 }else if(calls.some(x=>x.rva===0x1cf522d0))`);
const isolated=new Module(path.join(old,'r27_isolated_core.cjs'),module);
isolated.filename=path.join(old,'r27_isolated_core.cjs');isolated.paths=module.paths;
isolated._compile(core,isolated.filename);
const b=isolated.exports;
for(const d of [r14,r16])for(const s of JSON.parse(fs.readFileSync(path.join(d,'local_reader_schemas.json'),'utf8')))b.schemas.set(Number(s.rva),s);
for(const [r,mapping] of Object.entries(JSON.parse(fs.readFileSync(path.join(r14,'reader_dispatch.json'),'utf8')))){
 const table=[];for(const [ordinal,reader] of Object.entries(mapping))table[Number(ordinal)]={method:{rva:reader}};
 b.registries.set(Number(r),table);
}
const initial=new Set(b.schemas.keys()),local=path.join(out,'reader_schemas.json');
const owned=new Set(fs.existsSync(local)?JSON.parse(fs.readFileSync(local,'utf8')).map(s=>Number(s.rva)):[]);
if(fs.existsSync(local))for(const s of JSON.parse(fs.readFileSync(local,'utf8')))b.schemas.set(Number(s.rva),s);
const args=process.argv.slice(2);
if(args[0]==='inventory'){
 const names=new Set(['MonsterConfig','MonsterSkillConfig','MonsterTemplateConfig','MonsterAIConfig','CharacterConfig','TurnBasedAbilityConfigList']);
 const result=[];
 for(let i=0;i<84936;i++){
  const t=e.type(i);
  if(names.has(t.name)||/^(Monster(Row|ExcelTable|Config|Template|Skill|AI)|AIConfig|AISequence|AISelector)/.test(t.name))
   result.push({type:t,fields:e.fields(i),methods:e.methods(i)});
 }
 e.save('exact_type_inventory.json',{manifest_sha256:e.pin,source_files:e.manifest.files.filter(f=>['GameAssembly.dll','StarRail_Data/il2cpp_data/Metadata/global-metadata.dat'].includes(f.relative_path)),result});
 console.log(JSON.stringify(result.map(x=>({type:x.type,methods:x.methods.filter(m=>m.name.includes('Binary')||m.name==='OJNNBEJLDIJ'||m.name==='MGMEGEDLMAK')}))));
 }else if(args[0]==='switch'||args[0]==='branches'){
 const r=Number(args[1]),tx=rt.get(r).replaceAll('\r',''),lines=tx.split('\n');
 const bound=tx.match(/cmp\s+eax,0x([0-9a-f]+)\n[^\n]*ja\s+/);
 const table=tx.match(/lea\s+rcx,\[rip[^\n]+# 0x([0-9a-f]+)/);
 const mapping={},sites=[],targets=[];
 if(args[0]==='switch'){
  if(!bound||!table||!tx.includes('movsxd rax,DWORD PTR [rcx+rax*4]')||!tx.includes('add    rax,rcx'))throw Error('UNPROVEN_SWITCH_PATTERN');
  const count=parseInt(bound[1],16)+1,base=parseInt(table[1],16)-e.image;
  if(count>16)throw Error('SWITCH_BOUND');
  for(let i=0;i<count;i++)targets.push({i,target:base+e.dll.readInt32LE(e.off(base+i*4)),table_rva:e.hex(base+i*4)});
 }else {
  for(let j=0;j<lines.length-2;j++){
   const cmp=lines[j].match(/cmp\s+eax,0x([0-9a-f]+)/),jump=lines[j+1].match(/\s+(je|jne)\s+0x([0-9a-f]+)/);
   if(!cmp||!jump)continue;
   const next=lines[j+2].trim().match(/^([0-9a-f]+):/);
   targets.push({i:parseInt(cmp[1],16),target:parseInt(jump[1]==='je'?jump[2]:next[1],16)-e.image,
    compare_site:lines[j].trim().split(':')[0],branch_form:jump[1]});
  }
  for(let j=0;j<lines.length-2;j++)if(/test\s+eax,eax/.test(lines[j])&&/\s+jne\s+0x/.test(lines[j+1])){
   const next=lines[j+2].trim().match(/^([0-9a-f]+):/);
   if(next)targets.push({i:0,target:parseInt(next[1],16)-e.image,compare_site:lines[j].trim().split(':')[0],branch_form:'test-zero-fallthrough'});
  }
  if(!targets.length||targets.length>8)throw Error('BRANCH_BOUND');
 }
 for(const item of targets){
  const {i,target}=item;
  const at=lines.findIndex(l=>l.trim().startsWith((e.image+target).toString(16)+':'));
  if(at<0)throw Error('SWITCH_TARGET_OUTSIDE_METHOD');
  const jump=lines.slice(at).map(l=>l.match(/jmp\s+0x([0-9a-f]+)/)).find(Boolean);
  const child=jump?parseInt(jump[1],16)-e.image:0;
  const method=rt.map.has(child)?e.method(rt.map.get(child)):null;
  if(!method||!['OJNNBEJLDIJ','MGMEGEDLMAK','FromBinaryImpl'].includes(method.name))throw Error('SWITCH_CHILD_READER_UNPROVEN');
  mapping[i]=child;sites.push({...item,discriminator:i,branch:e.hex(target),reader:method});
 }
 const s={rva:e.hex(r),kind:'dispatch',type:e.method(rt.map.get(r)).type};b.schemas.set(r,s);
 const dp=path.join(out,'reader_dispatch.json'),maps=fs.existsSync(dp)?JSON.parse(fs.readFileSync(dp,'utf8')):{};
 maps[e.hex(r)]=mapping;e.save('reader_dispatch.json',maps);e.save('switch_'+r.toString(16)+'.json',{rva:e.hex(r),sites,manifest_sha256:e.pin});
 e.save('reader_schemas.json',[...b.schemas.values()].filter(s=>owned.has(Number(s.rva))||!initial.has(Number(s.rva))||Number(s.rva)===r));
 e.save('native_reader_receipt.json',receipt);console.log(JSON.stringify(sites));
 }else if(args[0]==='describe'){
 const rows=args.slice(1).map(a=>{const r=Number(a);const m=rt.map.has(r)?e.method(rt.map.get(r)):null;
  const tx=rt.map.has(r)?rt.get(r):e.disasm('method_'+r.toString(16),r,r+0x250);
  const u=require(path.join(old,'usage_map.cjs'));
  const globals=[...tx.matchAll(/mov\s+\w+,QWORD PTR \[rip.*# 0x([0-9a-f]+)/g)].map(x=>u.globalInfo(parseInt(x[1],16)-e.image)).filter(Boolean).map(g=>g.tag===6?{...g,generic:u.generic(g.index)}:g);
  return {rva:e.hex(r),method:m,fields:m?e.fields(m.type_index):[],globals};});
 e.save('native_descriptions_'+args.slice(1).map(a=>Number(a).toString(16)).join('_')+'.json',rows);
 e.save('native_reader_receipt.json',receipt);
 console.log(JSON.stringify(rows));
}else {
 for(const arg of args){const r=Number(arg);try{
  b.schemas.delete(r);const s=b.schema(r);
  if(s.kind==='dispatch'&&!b.registries.has(r))throw Error('UNPROVEN_DISPATCH');
  if(new Set((s.fields||[]).map(f=>BigInt(f.mask).toString())).size!==(s.fields||[]).length)throw Error('DUPLICATE_MASK_REQUIRES_CONTROL_FLOW_READER');
  for(const f of s.fields||[])if(typeof f.mask==='number'&&!Number.isSafeInteger(f.mask)){
   // Powers of two are exactly representable; retain integer strings for JSON.
   if(BigInt(f.mask)<=0n||(BigInt(f.mask)&(BigInt(f.mask)-1n)))throw Error('INEXACT_MASK');
   f.mask=BigInt(f.mask).toString();
  }
  receipt.attempts.push({rva:e.hex(r),status:'SCHEMA_EXTRACTED',type:s.type});
 }catch(err){receipt.attempts.push({rva:e.hex(r),status:'READER_GAP',question:String(err)});b.schemas.delete(r);}}
 e.save('reader_schemas.json',[...b.schemas.values()].filter(s=>owned.has(Number(s.rva))||!initial.has(Number(s.rva))||args.some(a=>Number(a)===Number(s.rva))));
 e.save('native_reader_receipt.json',{...receipt,method_bound:100,manifest_sha256:e.pin});
 console.log(JSON.stringify(receipt.attempts.slice(-args.length)));
}
