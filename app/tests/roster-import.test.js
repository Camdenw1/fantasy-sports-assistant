const assert = require('node:assert/strict');
const {parseRoster, leagueUrl} = require('../roster-import.js');
assert.deepEqual(parseRoster('Slot\tPlayer\tStatus\tPoints\nQB\tJosh Allen\tQ\t20'),
  [{slot:'QB',player:'Josh Allen',status:'Questionable'}]);
assert.equal(parseRoster('Player\tPos\nTest Player\tRB')[0].status,'Unknown');
assert.equal(parseRoster('RB | Test Player | ')[0].status,'Unknown');
assert.equal(parseRoster('BN | Test Player | Out')[0].slot,'BN');
assert.throws(()=>parseRoster('RB | Player | probable'),/unknown status/);
assert.throws(()=>parseRoster('QB\tName\tStatus\t20'),/labelled columns/);
assert.throws(()=>parseRoster('Slot\tPlayer\tStatus'),/no roster rows/);
assert.throws(()=>leagueUrl('javascript:alert(1)'),/https/);
assert.equal(leagueUrl('https://fantasy.espn.com/football/team?leagueId=1'), 'https://fantasy.espn.com/football/team?leagueId=1');
console.log('Roster parser checks passed');

const cbs='Players\n,Pos,Players,Opp\n,QB,Example Quarterback QB | BAL,TEN\nReserves\n,WR,Example Receiver WR | BUF,NE\nActive: 1 Reserve: 1\n';
const imported=parseRoster(cbs);
assert.equal(imported.length,2);
assert.equal(imported[0].player,'Example Quarterback');
assert.equal(imported[1].slot,'BN');
assert.equal(imported[1].status,'Unknown');
assert.throws(()=>parseRoster(cbs.replace('Active: 1 Reserve: 1','')),/incomplete/);
assert.throws(()=>parseRoster(cbs.replace('Reserve: 1','Reserve: 2')),/counts/);
assert.throws(()=>parseRoster(cbs.replace('Example Receiver WR | BUF','Example Quarterback WR | BUF')),/duplicate/);

assert.equal(imported[0].team,'BAL');
assert.equal(imported[1].position,'WR');
assert.equal(parseRoster('Slot | Player | Status | Position | Team\nBN | Test Player | Unknown | WR | BUF')[0].team,'BUF');
assert.equal(parseRoster('WR | Example \"Nickname\" Player | Active')[0].status,'Active');

assert.throws(()=>parseRoster(cbs+',RB,Extra Player RB | BUF,NE\n'),/after CBS roster totals/);
