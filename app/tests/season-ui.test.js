/* Verify async profile requests and failure advice gating without a browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.children=[]; this.value=''; this.dataset={}; this.options=[]; this.selectedOptions=[]; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children=items; }
  setAttribute() {}
  addEventListener() {}
  querySelector() { return this.children[0] || null; }
}
const elements=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const now=new Date().toISOString();
const snapshot={season:2026,start_week:5,end_week:17,fetched_at:now,source_updated_at:now,
  players:[{id:'1',name:'Fixture player',position:'RB',points:100,per_game:10,games:10,
    ownership:'mine',ranks:{FLEX:1,RB:1}}],profile:{label:'Fixture league'},
  roster:{fetched_at:now,issues:[],keepers:['1'],suggestions:[]}};
let state='ready';const urls=[];
const context=vm.createContext({document:{getElementById:get,querySelectorAll:()=>[],createElement:()=>new Element()},
  localStorage:{getItem:()=>null,setItem(){}},navigator:{},URLSearchParams,AbortController,
  setTimeout,clearTimeout,setInterval(){},console,
  fetch:async url=>{urls.push(url);return {ok:true,json:async()=>({status:state,data:{reports:[snapshot]},error:'Fixture outage'})};}});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../season.js'),'utf8'),context);
(async()=>{
  await vm.runInContext("profile='league:123';username='fixture';refresh()",context);
  const requested=new URL(urls.at(-1),'http://fixture');
  assert.equal(requested.searchParams.get('league_id'),'123');
  assert.equal(requested.searchParams.get('username'),'fixture');
  assert.equal(vm.runInContext('decisionIssues().length',context),0);
  assert.ok(get('season-rows').children.some(row=>row.className==='season-owned'));
  state='failed';
  await vm.runInContext('refresh(true)',context);
  assert.equal(vm.runInContext('data.players.length',context),1);
  assert.match(vm.runInContext('decisionIssues().join()',context),/Refresh unavailable/);
  state='ready';await vm.runInContext('refresh(true)',context);
  assert.equal(vm.runInContext('decisionIssues().length',context),0);
  console.log('Season UI profile, retained snapshot, advice gating, and recovery checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
