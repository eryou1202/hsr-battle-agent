// Static, pinned, bounded investigation of three inherited scheduler anchors.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const repo=path.resolve(__dirname,'../..');
const e=require(path.join(repo,'tmp/audit/r102_4651_structural_path_closure_20261004_001/exact.cjs'));
const out=path.join(repo,'tmp/audit/r21_true_turn_av_20261011_001');fs.mkdirSync(out,{recursive:true});
const save=(name,d)=>fs.writeFileSync(path.join(out,name),JSON.stringify(d,null,2)+'\n');
const anchors=['RPG.GameCore.TurnBasedGameMode','RPG.GameCore.BattleCharacterComponent','RPG.GameCore.TurnInsertAbility','RPG.GameCore.TurnInsertAction','RPG.GameCore.SetActionDelay','RPG.GameCore.ResetActionDelay'];
// Exact identity relocation only, not a global semantic/provider/registration search.
const types=[];for(let i=0;i<84936;i++){const t=e.type(i);if(anchors.includes(t.namespace+'.'+t.name))types.push({type:t,fields:e.fields(i),methods:e.methods(i)});}
if(process.argv[2]==='reachable'){
 const prior=JSON.parse(fs.readFileSync(path.join(out,'native_methods.json')));
 const ids=process.argv.slice(3).map(Number);
 const reached=new Set(prior.flatMap(x=>x.calls.flatMap(c=>c.identities.map(m=>m.type_index))));
 if(ids.some(i=>!reached.has(i)))throw Error('TYPE_NOT_DIRECTLY_REACHED');
 const result=ids.map(i=>({type:e.type(i),fields:e.fields(i),methods:e.methods(i)}));
 save('native_reachable_types.json',result);
 console.log(JSON.stringify(result.map(x=>({type:x.type,methods:x.methods.filter(m=>/Delay|Speed|TurnEnd|TurnStart|TurnOwner/.test(m.name))})),null,2));
}else if(process.argv[2]==='inventory'){
 save('native_anchor_inventory.json',{source_version:'4.6.51',manifest_sha256:e.pin,anchors,
  source_files:e.manifest.files.filter(f=>['GameAssembly.dll','StarRail_Data/il2cpp_data/Metadata/global-metadata.dat'].includes(f.relative_path)),
  types,lookup_scope:'exact named inherited anchor identities only; no global reverse discovery'});
 console.log(JSON.stringify(types.map(x=>({type:x.type,methods:x.methods.filter(m=>/ActionDelay|Turn|Speed|Insert|Finish|Revive|Death|ActiveEntity|ActionOrder/.test(m.name))})),null,2));
}else{
 const ids=process.argv.slice(2).map(Number);if(ids.length>120)throw Error('METHOD_BUDGET');
 const selectedPath=path.join(out,'native_methods.json');const prior=fs.existsSync(selectedPath)?JSON.parse(fs.readFileSync(selectedPath)):[];
 if(new Set([...prior.map(x=>x.method.index),...ids]).size>120)throw Error('TOTAL_METHOD_BUDGET');
 const map=new Map();for(let i=0;i<772632;i++){let r=Number(e.dll.readBigUInt64LE(e.pt+i*8))-e.image;if(r>0){if(!map.has(r))map.set(r,[]);map.get(r).push(i);}}
 const starts=[...map.keys()].sort((a,b)=>a-b);
 const rows=ids.filter(i=>!prior.some(p=>p.method.index===i)).map(i=>{
  const m=e.method(i);if(!m.rva)throw Error('NO_NATIVE_BODY '+i);const r=Number(m.rva),end=starts.find(x=>x>r);
  if(!end||end-r>0x10000)throw Error('BOUNDED_METHOD_ONLY');
  const s=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
  const file='native_'+i+'_'+r.toString(16)+'.txt';fs.writeFileSync(path.join(out,file),s);
  return {method:m,end_rva:e.hex(end),bounded_span:end-r,body_file:file,body_sha256:e.sha(Buffer.from(s)),
   calls:[...s.matchAll(/([0-9a-f]+):\s+(call|jmp)\s+0x([0-9a-f]+)/g)].map(x=>({site:e.hex(parseInt(x[1],16)-e.image),kind:x[2],target:e.hex(parseInt(x[3],16)-e.image),identities:(map.get(parseInt(x[3],16)-e.image)||[]).map(j=>e.method(j))}))};
 });save('native_methods.json',[...prior,...rows]);
 console.log(JSON.stringify(rows.map(x=>({method:x.method,span:x.bounded_span,calls:x.calls.filter(c=>c.identities.length).map(c=>({site:c.site,identities:c.identities.map(m=>({index:m.index,type:m.type,name:m.name}))}))})),null,2));
}
