const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag='',text=''){this.tag=tag;this.children=[];this._text=text;this.listeners={};this.classList={add(){}};this.style={setProperty(){}};}
  append(...items){this.children.push(...items);}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>typeof c==='string'?c:c.textContent).join('');}
  setAttribute(){}
  addEventListener(type,fn){this.listeners[type]=fn;}
}
const report={league:{id:'fixture',name:'Fixture league'},team:{roster_id:1,name:'Mine'},totals:{current:20}};
let calls=[],handler=async url=>{if(url.endsWith('/users'))return [{user_id:'u',display_name:'Mine'}];if(url.endsWith('/rosters'))return [{roster_id:1,owner_id:'u',settings:{}}];throw Error('Offline');};
const context=vm.createContext({window:{matchMedia:()=>({matches:true})},document:{hidden:true,addEventListener(){}},
  state:{view:'scores',reports:[report],manual:[]},Date,console,setTimeout:()=>1,clearTimeout(){},
  getJson:async url=>{calls.push(url);return handler(url);},render(){},activeWeek:()=>9,allReports:()=>[report],liveManual:()=>false,
  node:(tag,cls,text='')=>new Element(tag,text),add:(p,...c)=>{p.append(...c);return p;},number:v=>v==null?'—':String(v),age:()=> '2m ago',dateTime:v=>v,
  teamMark:()=>null,refreshEspn:async()=>{},localStorage:{getItem:()=>null}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../live.js'),'utf8'),context);
const run=code=>vm.runInContext(code,context);
(async()=>{
  context.report=report;
  await run('loadLeagueScores(report,9)');
  assert.equal(run('live.leagues.fixture.error!=null'),true);
  const failedCalls=calls.length;
  for(let i=0;i<5;i++)run('renderScores(node("main"))');
  assert.equal(calls.length,failedCalls,'Rendering an outage must not create a retry loop');
  assert.match(run('const screen=node("main");renderScores(screen);screen.textContent'),/Refresh scores/);
  handler=async()=>[{roster_id:1,matchup_id:1,points:12},{roster_id:2,matchup_id:1,points:8}];
  await run('loadLeagueScores(report,9,true)');
  assert.equal(run('live.leagues.fixture.games[0][0].points'),12);
  const savedAt=run('live.leagues.fixture.at');
  handler=async()=>{throw Error('Offline');};
  await run('loadLeagueScores(report,9,true)');
  assert.equal(run('live.leagues.fixture.at'),savedAt,'An outage must not restamp saved scores');
  assert.equal(run('live.leagues.fixture.games[0][0].points'),12);
  await run('loadLeagueScores(report,10,true)');
  assert.equal(run('live.leagues.fixture.games'),undefined,'A different week must not reuse old scores');
  // An older in-flight response cannot replace a newer week.
  let finishOld;
  handler=url=>url.endsWith('/matchups/9') ? new Promise(resolve=>finishOld=resolve) : Promise.resolve([{roster_id:1,matchup_id:1,points:30}]);
  const old=run('loadLeagueScores(report,9,true)');
  await run('loadLeagueScores(report,10,true)');
  finishOld([{roster_id:1,matchup_id:1,points:1}]);await old;
  assert.equal(run('live.leagues.fixture.week'),10);
  assert.equal(run('live.leagues.fixture.games[0][0].points'),30);
  handler=async()=>({players:{}});calls=[];
  for(let i=0;i<5;i++)assert.equal(await run('loadPlayerNames(["unknown","0"])'),false);
  assert.equal(calls.length,1,'Missing player identities must be throttled');
  // Concurrent calls share an existing request, then recover with complete data.
  let finish;
  handler=()=>new Promise(resolve=>finish=resolve);calls=[];
  const first=run('loadLeagueScores(report,10,true)');
  await run('loadLeagueScores(report,10,true)');assert.equal(calls.length,1);
  finish([{roster_id:1,matchup_id:1,points:40}]);await first;
  assert.equal(run('live.leagues.fixture.error'),null);
  handler=async()=>[];
  await run('loadLeagueScores(report,10,true)');
  assert.equal(run('live.leagues.fixture.games[0][0].points'),40,'Empty responses must retain last good scores');
  calls=[];await run('poll()');assert.equal(calls.length,0,'Hidden tabs should not fetch');
  run('document.hidden=false');
  handler=()=>new Promise(resolve=>finish=resolve);calls=[];
  const polling=run('poll()');await run('poll()');assert.equal(calls.length,1,'Only one poll may run at a time');
  handler=async()=>[{roster_id:1,matchup_id:1,points:45}];
  finish({week:9,games:[]});await polling;
  console.log('Live score outage, week isolation, recovery and request throttling checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
