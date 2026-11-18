const e=require('../../tmp/audit/r102_4651_structural_path_closure_20261004_001/exact.cjs');
const fs=require('fs');let rows=[];for(let i=0;i<84936;i++){let t=e.type(i);if(/SetDynamicValueBy(Property|CharacterCount)|FireProjectile|SetTeamFormation|ByDistance/.test(t.name))rows.push({type:t,fields:e.fields(i),methods:e.methods(i)});}
fs.writeFileSync('tmp/audit/r28_original_combat_semantics_20261022_001/target_types.json',JSON.stringify(rows,null,2));console.log(rows.map(x=>({type:x.type.name,index:x.type.index,methods:x.methods.map(m=>({name:m.name,rva:m.rva}))})));
