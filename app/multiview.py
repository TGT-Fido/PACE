"""PACE 6 view state and relationships. Layouts never change filesystem paths."""
import copy, math, uuid
VIEWS=('cards','canvas','radial','roadmap')

def defaults():
    return {'revision':0,'startup':'cards','parents':{},'links':[],
            'layouts':{name:{'positions':{},'collapsed':[],'focus':'root','camera':None} for name in VIEWS if name!='cards'}}

def extend(Base,atomic_json):
 class Store(Base):
    def __init__(self,data):
        super().__init__(data)
        if 'visual' not in self.state:
            self.state['visual']=defaults();self.save()

    def scan(self):
        result=super().scan()
        result['visual']=copy.deepcopy(self.state.get('visual',defaults()))
        return result

    def visual_update(self,body):
        with self.lock:
            snapshot=self.scan();current=self.state.setdefault('visual',defaults())
            if body.get('revision')!=current['revision']: raise ValueError('View settings changed on another device. Refresh and try again.')
            visual=copy.deepcopy(current);action=body.get('action')
            projects={p['id']:p for p in snapshot['projects']}
            groups={'group:'+c for c in snapshot['categories']}
            known={'root'}|groups|set(projects)
            def valid_node(node):
                if node not in known: raise ValueError('Project or group is no longer available')
                return node
            if action=='startup':
                if body.get('view') not in VIEWS: raise ValueError('Unknown view')
                visual['startup']=body['view']
            elif action=='parent':
                child=body.get('child');parent=body.get('parent')
                if child not in projects: raise ValueError('Only projects can be assigned a parent')
                if parent is None:visual['parents'].pop(child,None)
                else:
                    valid_node(parent)
                    if parent==child:raise ValueError('A project cannot be its own parent')
                    cursor=parent;seen={child}
                    while cursor in projects:
                        if cursor in seen:raise ValueError('This would create a circular parent/child relationship')
                        seen.add(cursor);cursor=visual['parents'].get(cursor,'group:'+projects[cursor]['category'])
                    visual['parents'][child]=parent
            elif action=='link':
                source=valid_node(body.get('from'));target=valid_node(body.get('to'))
                if source==target:raise ValueError('Choose two different nodes')
                label=body.get('label','Related')
                if not isinstance(label,str) or len(label)>100:raise ValueError('Link label must be at most 100 characters')
                if len(visual['links'])>=1000:raise ValueError('Maximum 1,000 related links')
                directed=body.get('directed',False)
                if not isinstance(directed,bool):raise ValueError('Invalid arrow choice')
                for edge in visual['links']:
                    if edge['from']==source and edge['to']==target and edge['label']==label:raise ValueError('That link already exists')
                visual['links'].append({'id':str(uuid.uuid4()),'from':source,'to':target,'label':label,'directed':directed})
            elif action=='unlink':
                if not any(e['id']==body.get('id') for e in visual['links']):raise ValueError('Link no longer exists')
                visual['links']=[e for e in visual['links'] if e['id']!=body['id']]
            elif action in {'layout','reset'}:
                view=body.get('view')
                if view not in visual['layouts']:raise ValueError('Choose a map view')
                if action=='reset':visual['layouts'][view]=defaults()['layouts'][view]
                else:
                    layout=visual['layouts'][view]
                    if 'positions' in body:
                        positions=body['positions']
                        if not isinstance(positions,dict) or len(positions)>5000:raise ValueError('Invalid positions')
                        for key,p in positions.items():
                            valid_node(key)
                            if not isinstance(p,dict) or set(p)!={'x','y'} or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>100000 for v in p.values()):raise ValueError('Invalid node position')
                        layout['positions'].update(positions)
                    if body.get('clear_positions') is True:layout['positions']={}
                    if 'collapsed' in body:
                        values=body['collapsed']
                        if not isinstance(values,list) or len(values)>5000:raise ValueError('Invalid collapsed branches')
                        layout['collapsed']=list(dict.fromkeys(valid_node(n) for n in values))
                    if 'focus' in body:layout['focus']=valid_node(body['focus'])
                    if 'camera' in body:
                        c=body['camera']
                        if c is not None and (not isinstance(c,dict) or set(c)!={'x','y','scale'} or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in c.values()) or not .08<=c['scale']<=4 or abs(c['x'])>100000 or abs(c['y'])>100000):raise ValueError('Invalid camera')
                        layout['camera']=c
            else:raise ValueError('Unknown view action')
            visual['revision']+=1
            self.state['visual']=visual;self.save()
            return copy.deepcopy(visual)

    def settings(self,body):
        # Category rename preserves references and each independent layout.
        with self.lock:
            old=copy.deepcopy(self.state.get('visual',defaults()))
            result=super().settings(body)
            if body.get('kind')=='category' and body.get('action') in {'rename','delete'}:
                source='group:'+body['name'];target='group:'+body.get('new_name','Other')
                visual=self.state.setdefault('visual',old)
                visual['parents']={k:target if v==source else v for k,v in visual['parents'].items()}
                for edge in visual['links']:
                    for key in ('from','to'):
                        if edge[key]==source:edge[key]=target
                visual['links']=[e for e in visual['links'] if e['from']!=e['to']]
                for layout in visual['layouts'].values():
                    if source in layout['positions']:layout['positions'].setdefault(target,layout['positions'].pop(source))
                    layout['collapsed']=list(dict.fromkeys(target if n==source else n for n in layout['collapsed']))
                    if layout['focus']==source:layout['focus']=target
                visual['revision']+=1;self.save()
            return result

    def restore(self,name):
        previous=self.state.get('visual',defaults())['revision']
        result=super().restore(name)
        # Older backups may not contain view state; advance revision after all restores.
        self.state.setdefault('visual',defaults())
        self.state['visual']['revision']=max(previous,self.state['visual']['revision'])+1;self.save()
        return result
 return Store
