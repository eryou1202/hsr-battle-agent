// Pinned, bounded static evidence. No live process or inherited artifact writes.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),base=path.join(root,'tmp/audit/r102_4651_structural_path_closure_20261004_001');
const e=require(path.join(base,'exact.cjs')),out=path.join(root,'tmp/audit/r31_original_task_breakthrough_20261108_001');
const save=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2)+'\n');
if(process.argv[2]==='metadata'){
 const candidates=[],predicates=[];
 for(let i=0;i<84936;i++){
  const methods=e.methods(i);
  // Name matches are discovery candidates only, never an interface-offset join.
  if(methods.some(m=>m.name.includes('FFKBNBIMMHE')))candidates.push({type:e.type(i),fields:e.fields(i),methods});
  const t=e.type(i);
  if(t.name==='ByCompareTarget')predicates.push({type:t,fields:e.fields(i),methods});
 }
 const ids=new Set(predicates.map(t=>t.type.index)),holders=[];
 for(let i=0;i<84936;i++){const fields=e.fields(i).filter(f=>[17,18].includes(f.type?.kind)&&ids.has(f.type.data));if(fields.length)holders.push({type:e.type(i),fields,methods:e.methods(i)});}
 save('metadata.json',{pin:e.pin,interface:e.type(10867),interface_methods:e.methods(10867),candidates,census_status:'NAME_DISCOVERY_ONLY_INTERFACE_OFFSET_ENUMERATION_UNAVAILABLE',predicates,holders});
 console.log(JSON.stringify({candidates:candidates.map(t=>t.type),predicates,holders}));
}else if(process.argv[2]==='xref'){
 const u=require(path.join(base,'usage_map.cjs')),rt=require(path.join(base,'reader_tools.cjs')),globals=new Set(),rows=[];
 for(let i=0;i<u.range(328749);i++){const p=u.pair(i);if(p.tag===1&&p.global_rva){const t=e.typeRef(p.index);if(t?.data===23409&&t.kind===18)globals.add(Number(p.global_rva));}}
 for(const s of e.sections.filter(s=>s.name==='il2cpp'))for(let p=s.raw;p<s.raw+s.raw_size-7;p++)if((e.dll[p]===0x48||e.dll[p]===0x4c)&&e.dll[p+1]===0x8b&&(e.dll[p+2]&0xc7)===5){const site=s.rva+p-s.raw,target=site+7+e.dll.readInt32LE(p+3);if(globals.has(target)){let lo=0,hi=rt.starts.length;while(lo<hi){const m=(lo+hi)>>1;if(rt.starts[m]<=site)lo=m+1;else hi=m;}rows.push({site:e.hex(site),global:e.hex(target),method:e.method(rt.map.get(rt.starts[lo-1]))});}}
 save('jade_config_xrefs.json',{pin:e.pin,rows});console.log(JSON.stringify(rows));
}else{
 const rt=require(path.join(base,'reader_tools.cjs'));
 const p=path.join(out,'native_methods.json'),receipt=fs.existsSync(p)?JSON.parse(fs.readFileSync(p)):{pin:e.pin,limit:20,methods:[]};
 for(const arg of process.argv.slice(2)){
  const r=Number(arg);if(receipt.methods.some(m=>m.rva===e.hex(r)))continue;
  if(receipt.methods.length>=20)throw Error('BUDGET');
  const end=rt.starts.find(x=>x>r);if(!rt.map.has(r)||end-r>0x10000)throw Error('BOUND');
  const tx=cp.execFileSync('objdump',['-D','-Mintel','--no-show-raw-insn','--start-address='+e.hex(e.image+r),'--stop-address='+e.hex(e.image+end),path.join(e.root,'GameAssembly.dll')],{encoding:'utf8',maxBuffer:4*1024*1024});
  const artifact='method_'+r.toString(16)+'.txt';fs.writeFileSync(path.join(out,artifact),tx);
  const calls=[...tx.matchAll(/([0-9a-f]+):\s+(call|jmp)\s+0x([0-9a-f]+)/g)].map(x=>{const t=parseInt(x[3],16)-e.image;return {site:e.hex(parseInt(x[1],16)-e.image),target:e.hex(t),method:rt.map.has(t)?e.method(rt.map.get(t)):null};});
  const m={rva:e.hex(r),end:e.hex(end),method:e.method(rt.map.get(r)),artifact,sha256:e.sha(Buffer.from(tx)),calls};receipt.methods.push(m);console.log(JSON.stringify(m));
 }
 save('native_methods.json',receipt);
}
