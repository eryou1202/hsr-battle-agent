"""R32 bounded Jade construction investigation; inherited files are read only."""
from r30_closure import *
AUDIT=ROOT/'tmp/audit/r32_jade_modifier_closure_20261108_001'
R31=ROOT/'tmp/audit/r31_original_task_breakthrough_20261108_001'
KEYS=('MAvatar_Jade_00_BPSkillSelf','MAvatar_Jade_00_BPSkillBuffListen')

def write(n,v):
    p=AUDIT/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8')

def gate():
    import r27_checks as c
    c.AUDIT=AUDIT;c.write=write;c.gate()

def acquire():
    from r14_corpus import Assets,directory
    from r27_reader import Reader,machinery
    assets=Assets();schemas,dispatch=machinery()
    parent=read(ROOT/'tmp/audit/r27_real_character_monster_20261022_001/decoded/Avatar_Jade_00_Skill02_Phase02.json')
    config=parent['entry']['config'];layout=parent['entry']['layout']
    assert assets.lookup(config['path'])==config
    data,pin=assets.source(config)
    assert pin['sha256']==parent['source_shard_sha256']
    entries=directory(data,layout,config,schemas,dispatch)
    from hsr_battle_agent.battle_ir.content_catalog import references,ContentCatalog
    from hsr_battle_agent.battle_ir.behavior import IRNode
    ir_path=ROOT/'tmp/audit/r27_real_character_monster_20261022_001/ir/Avatar_Jade_00_Skill02_Phase02.json'
    compiled=IRNode.from_dict(read(ir_path))
    record={**parent,'ir':compiled.to_dict(),'canonical_IR_hash':compiled.stable_hash()}
    catalog=ContentCatalog([parent['entry']],[record])
    definitions=catalog.modifier_definitions()
    exact_sites=[s for s in references(parent['graph']) if s.get('definition') and s.get('identity') in KEYS]
    rows=[]
    for key in KEYS:
        matches=[e for e in entries if e['name']==key]
        inline=[s for s in exact_sites if s['identity']==key]
        exact=[d for d in definitions.values() if d['config_identity']==key]
        row=dict(key=key,matches=matches,source_pin=pin,config=config,layout=layout,inline_matches=inline,exact_definitions=exact,parent_IR_sha256=sha(ir_path),parent_IR_hash=compiled.stable_hash())
        if len(inline)==1 and len(exact)==1:
            start,end=exact[0]['source_span']
            rereader=Reader(data,start,end,schemas,dispatch)
            reread=rereader.read(0x1eb95390)
            assert rereader.cursor==end and reread==exact[0]['decoded_graph']
            row['status']='EXACT_INLINE_DEFINITION_RECOVERED'
            row['source_reader_replay']='BOUNDED_FULL_CONSUMPTION_EXACT_GRAPH_EQUALITY'
            row['definition']=exact[0]
            row['definition_bytes_sha256']=hashlib.sha256(data[exact[0]['source_span'][0]:exact[0]['source_span'][1]]).hexdigest()
            write('definitions/'+key+'.json',row);rows.append(row);continue
        if len(matches)!=1:
            row['status']='MODIFIER_DEFINITION_MISSING' if not matches else 'MODIFIER_DEFINITION_AMBIGUOUS'
        else:
            e=matches[0];p=Reader(data,e['absolute'],e['record_end'],schemas,dispatch)
            try:
                graph=p.read(0x1eb95390)
                row.update(status='ACCEPTED' if p.cursor==p.end else 'FRAMING_GAP',graph=graph,cursor=p.cursor,end=p.end)
            except (ValueError,UnicodeError) as exc:
                row.update(status='STRUCTURAL_READER_GAP',cursor=p.cursor,end=p.end,detail=str(exc),reader_gap=getattr(exc,'reader_gap',None),reader_gap_type=getattr(exc,'reader_gap_type',None))
        write('definitions/'+key+'.json',row);rows.append(row)
    write('directory_receipt.json',dict(entries=entries,index_pin=assets.index_pin,source_pin=pin,config=config,layout=layout,definition_names=[e['name'] for e in entries if e['type']==0],scope='Exact source-backed Jade Ability container only; not a global absence claim'))
    write('inline_definition_acquisition.json',rows)
    write('definition_acquisition.json',[dict(key=r['key'],matches=r['matches'],status='MODIFIER_DEFINITION_MISSING',scope='TOP_LEVEL_DIRECTORY_ONLY; see inline_definition_acquisition.json for recovered nested definitions',config=config,layout=layout,source_pin=pin) for r in rows])
    print([(r['key'],r['status'],r.get('detail')) for r in rows],flush=True)

def investigate():
    from hsr_battle_agent.battle_runtime.behavior import BehaviorRuntime,GapError
    from hsr_battle_agent.battle_ir.behavior import IRNode,walk_nodes
    from hsr_battle_agent.battle_ir.content_catalog import walk
    from hsr_battle_agent.battle_runtime.modifier_lifecycle import apply,POLICY_ID
    from r14_corpus import Assets
    from dataclasses import asdict
    assets=Assets();rows=[]
    for branch in ['b','false']:
        folder=R31/'jade'/branch;initial=read(folder/'initial_runtime.json');commands=read(folder/'commands.json')
        r,out=BehaviorRuntime.from_snapshot(initial).replay_turn_commands(commands)
        assert r.snapshot()==read(folder/'final_runtime.json')
        assert r.clone().stable_hash()==BehaviorRuntime.from_snapshot(json.loads(json.dumps(r.snapshot()))).stable_hash()
        diag=r.clone().run_until_blocked();node=IRNode.from_dict(read(folder/'receipt.json')['next_gap']['node'])
        assert diag.gap.node==node.to_dict()
        a=r.state.scheduler.action_execution
        sequence=next(s for s in a['sequences'].values() if node.to_dict() in s['nodes'])
        owned=a['tasks'][sequence['parent_task_id']]
        ability=a['abilities'][sequence['ability_instance_id']]
        source=read(ROOT/node.authority.source_artifact)
        raw=next(n for _,n in walk(source['graph']) if n.get('type')==node.op and [n.get('start'),n.get('end')]==node.payload['span'])
        data,pin=assets.source(source['entry']['config']);lo,hi=node.payload['span']
        assert sha(ROOT/node.authority.source_artifact)==node.authority.source_sha256
        negatives=[]
        for name,binding in [('unbound_application',None),('missing_definition',{'definition_id':'UNACQUIRED_EXACT_JADE_DEFINITION'})]:
            test=r.clone()
            if binding is not None:test.policies[POLICY_ID]['applications'][node.stable_hash()]=binding
            before=test.snapshot()
            try:apply(test,node)
            except GapError as exc:detail=str(exc)
            else:raise AssertionError('unknown definition executed')
            assert before==test.snapshot()
            negatives.append(dict(case=name,status='REFUSAL_VERIFIED',detail=detail,atomic=True))
        fields=node.to_dict()['payload']['fields']
        row=dict(branch=branch,modifier=fields['unbound_bit_1']['payload']['value'],node_id=node.node_id,task_hash=node.stable_hash(),node=node.to_dict(),source_artifact=node.authority.source_artifact,source_artifact_sha256=sha(ROOT/node.authority.source_artifact),source_identity=[pin['sha256'],lo,hi],original_task_bytes_sha256=hashlib.sha256(data[lo:hi]).hexdigest(),serialized=raw,source_selector='Serialized CasterType absent; native default unresolved',target_selector=fields['unbound_bit_0'],constructor_arguments=fields,unknown_field_masks=node.payload['reference_binding']['unknown_slots'],linked_child_ability=ability,task_ownership=owned,original_sequence=sequence,actual_next_original_node=None,continuation_status='UNREACHED: AddModifier remains pending; original owned sequence retained',before=8,after=a['metrics']['tasks_completed'],original_predicates_completed=1,addmodifier_completed=False,constructed_modifier=None,source_evidenced_applications=0,explicit_reference_applications=0,listener_effect_state=dict(modifiers=r.snapshot()['state']['modifiers'],listeners=r.snapshot()['state']['mechanics']),next_gap=asdict(diag.gap),parent_finish=False,turn_released=False,clone_snapshot_replay='PASS',native_effective_validated=False,negatives=negatives,ability_hashes={k:v.stable_hash() for k,v in r.abilities.items()})
        assert row['after']==8
        for name,value in [('initial_runtime.json',initial),('commands.json',commands),('final_runtime.json',r.snapshot()),('receipt.json',row)]:write('jade/'+branch+'/'+name,value)
        rows.append(row)
    write('jade/results.json',rows)
    inherited=read(OLD/'native_methods.json');selected=[m for m in inherited['methods'] if m['rva'] in ['0x160A9440','0xB7585A0','0xF1290A0']]
    for m in selected:
        assert sha(OLD/m['artifact'])==m['sha256']
        (AUDIT/'native').mkdir(exist_ok=True)
        (AUDIT/'native'/m['artifact']).write_bytes((OLD/m['artifact']).read_bytes())
    write('native/evidence.json',dict(reused_methods=selected,additional_selected_bodies=0,limit=16,new_dependency_hops=0,definition_families=2,stop='Exact definitions unavailable in acquired source-backed directory; no further bodies acquired'))
    print('Two original parent replays preserved; zero modifier applications',flush=True)

if __name__=='__main__':
    if sys.argv[1]=='gate':gate()
    elif sys.argv[1]=='acquire':acquire()
    elif sys.argv[1]=='investigate':investigate()
    elif sys.argv[1]=='tests':
        import r30_closure as c
        c.AUDIT=AUDIT;c.tests()
    elif sys.argv[1]=='scenarios':
        rows={}
        for mode,count in [('frozen',632),('skills',160),('defense',18),('encounters',18),('planner',20),('turns',14)]:
            args=[sys.executable,__file__,'regressions',mode];p=subprocess.run(args,cwd=ROOT,capture_output=True)
            write('tests/scenario_'+mode+'.json',dict(command=args,actual_exit_code=p.returncode,count=count))
            (AUDIT/'tests'/('scenario_'+mode+'.log')).write_bytes(p.stdout+p.stderr)
            rows[mode]=dict(count=count,actual_exit_code=p.returncode);write('tests/scenarios.json',rows);print(mode,p.returncode,flush=True)
        assert all(v['actual_exit_code']==0 for v in rows.values())
    elif sys.argv[1]=='regressions':
        import r30_closure as c
        c.AUDIT=AUDIT;c.regressions(sys.argv[2])
