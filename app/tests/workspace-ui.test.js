const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element {
  constructor(tag='div') {this.tag=tag;this.children=[];this.value='';this.dataset={};this.hidden=false;this.listeners={};this.classList={toggle(){}};this._text='';}
  get textContent(){return this._text+this.children.map(c=>typeof c==='string' ? c : c.textContent).join('');}
  set textContent(v){this._text=String(v);this.children=[];}
  get options(){return this.children.filter(c=>c.tag==='option');}
  append(...items){this.children.push(...items);}
  prepend(...items){this.children.unshift(...items);}
  replaceChildren(...items){this._text='';this.children=items;}
  setAttribute(){}
  addEventListener(name,handler){this.listeners[name]=handler;}
  querySelector(){return new Element('button');}
  reset(){}
  scrollIntoView(){}
  matches(){return false;}
}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const now=new Date().toISOString(),player=(id,name)=>({id,name,pos:'RB',sources:1,value:10,team:'DET',game_state:'pre'});
const starter=player('1','Fixture starter'),bench=player('2','Fixture bench'),reserve={...player('3','Fixture reserve'),injury:'IR'};
const report={schema:'startsit/v1',league:{id:'123',name:'Fixture league',season:2026,week:5,scoring_fingerprint:{rec:.5}},team:{name:'Fixture team'},
  slots:[{slot:'RB',current:starter,recommended:starter,locked:false}],bench:[bench],reserve:[reserve],swaps:[],alerts:[],
  sources:{schedule:'espn scoreboard',projections:['fixture'],projection_gaps:[]},totals:{current:10,recommended:10},apply:{url:'https://sleeper.com/leagues/123/team'}};
const data={engine_version:3,reports:[report],freshness:{roster_fetched_at:now,player_list_fetched_at:now}};
let espnResponse={needs_team:true,teams:[{id:7,name:'Team by name'}]};
const saved=new Map([['fantasy-sleeper-connection',JSON.stringify({username:'fixture',leagueId:'123'})],['fantasy-last-lineups-v1',JSON.stringify({...data,username:'fixture'})]]);
const location={hash:'#home'},context=vm.createContext({document:{getElementById:get,createElement:t=>new Element(t),querySelectorAll:()=>[],querySelector:()=>get("context-bar"),addEventListener(){}},
  window:{scrollTo(){},addEventListener(){}},location,history:{replaceState(a,b,hash){location.hash=hash;}},
  localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)},navigator:{},URLSearchParams,AbortController,setTimeout,clearTimeout,
  crypto:{randomUUID:()=> 'import-id'},RosterImport:{parseRoster:()=>[],leagueUrl:x=>x},
  fetch:async url=>({ok:true,json:async()=>url.startsWith('/api/espn?') ? espnResponse : url==='/api/season-state' ? {season:2026,week:5} : {status:'ready',data}})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8'),context);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  vm.runInContext("selectLeague('s:123')",context);
  assert.match(get('content').textContent,/Bench · 1BNFixture bench/);
  assert.match(get('content').textContent,/Reserve · 1RESFixture reserve/);
  vm.runInContext("state.reports[0].sources.projection_gaps=[{name:'Missing fixture'}];setView('home')",context);
  assert.match(get('content').textContent,/Review league dataMissing projections: Missing fixture/);
  assert.match(get('content').textContent,/Refresh data/);
  assert.match(get('content').textContent,/Check your injured playersFixture reserve · IR/);
  vm.runInContext("choosePlatform('CBS')",context);
  assert.equal(get('sleeper-connect-panel').hidden,true);
  assert.equal(get('espn-connect-panel').hidden,true);
  assert.equal(get('manual-import').open,true);
  assert.equal(get('manual-platform').value,'CBS');
  // Updating a manual snapshot must preserve its bench in the editable roster.
  vm.runInContext("editManual({id:'manual',name:'Fixture CBS',platform:'CBS',week:5,starters:[{slot:'RB',player:'Starter',status:'Active'}],bench:[{slot:'BN',player:'Bench',status:'Active'}]})",context);
  assert.match(get('manual-starters').value,/BN \| Bench \| Active/);
  get('espn-url').value='https://fantasy.espn.com/football/league?leagueId=1';
  await get('espn-form').listeners.submit({preventDefault(){}});
  assert.equal(get('espn-team-label').hidden,false);
  assert.equal(get('espn-team').options[1].textContent,'Team by name');
  assert.equal(get('espn-team').options[1].value,7);
  get('espn-team').value='7';
  espnResponse={needs_team:false,snapshot:{name:'Fixture ESPN',platform:'ESPN',teamName:'Team by name',week:5,
    starters:[{slot:'RB',player:'Starter',status:'Active'}],bench:[{slot:'BN',player:'Bench',status:'Active'}],savedAt:now}};
  await get('espn-form').listeners.submit({preventDefault(){}});
  assert.equal(vm.runInContext('state.manual[0].bench.length',context),1);
  assert.equal(vm.runInContext('state.view',context),'lineup');
  assert.match(get('content').textContent,/Bench · 1BNBench/);
  console.log('Workspace bench, reserve, visible Home actions, and guided connection checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
