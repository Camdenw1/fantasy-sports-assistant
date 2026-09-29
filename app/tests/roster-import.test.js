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
