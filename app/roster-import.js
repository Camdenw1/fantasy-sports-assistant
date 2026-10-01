/* Roster snapshots: parse explicit columns, never guess a player's identity. */
(function (root) {
  const statuses = {active:"Active", healthy:"Active", q:"Questionable", questionable:"Questionable",
    d:"Doubtful", doubtful:"Doubtful", o:"Out", out:"Out", ir:"IR", pup:"PUP", sus:"Sus",
    bye:"Bye", empty:"Empty", unknown:"Unknown", "":"Unknown"};
  function parseRoster(text, required = true) {
    if (text.length > 500000) throw new Error('Import one roster, not an entire league export.');
    const csv=/^.*,(?:\s*"?pos"?\s*|\s*"?players"?\s*),.*$/im.test(text) ? parseCSV(text) : [];
    const cbsHeader=csv.findIndex(row=>row.some(v=>v.trim().toLowerCase()==='players') && row.some(v=>v.trim().toLowerCase()==='pos'));
    if(cbsHeader>=0) return parseCBS(csv,cbsHeader);
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    if (required && !lines.length) throw new Error("Paste a roster before saving.");
    if (!lines.length) return [];
    const split = line => line.split(line.includes("\t") ? "\t" : "|").map(value => value.trim());
    const first = split(lines[0]).map(value => value.toLowerCase());
    const headerPlayer = first.findIndex(value => ["player", "name", "player name"].includes(value));
    const headerSlot = first.findIndex(value => ["slot", "position", "pos"].includes(value));
    const headerStatus = first.findIndex(value => ["status", "injury", "injury status"].includes(value));
    const headerPosition=first.indexOf('position'), headerTeam=first.indexOf('team');
    const hasHeader = headerPlayer >= 0 && headerSlot >= 0;
    const data = hasHeader ? lines.slice(1) : lines;
    if (required && !data.length) throw new Error("The table has headers but no roster rows.");
    if (data.length > 80) throw new Error("Paste one team's roster, with at most 80 rows.");
    return data.map((line, index) => {
      const parts = split(line);
      if (!hasHeader && parts.length !== 3) throw new Error("Row " + (index + 1) + ": use slot | player | status, or a table with labelled columns.");
      const slot = parts[hasHeader ? headerSlot : 0], player = parts[hasHeader ? headerPlayer : 1];
      const rawStatus = (parts[hasHeader ? headerStatus : 2] || "").toLowerCase();
      if (!slot || !player) throw new Error("Row " + (index + 1) + ": slot and player are required.");
      const status = statuses[rawStatus];
      if (status == null) throw new Error("Row " + (index + 1) + ": unknown status '" + rawStatus + "'. Review this row instead of guessing.");
      if (slot.length > 30 || player.length > 80) throw new Error("Row " + (index + 1) + ": this looks like more than a slot and player name.");
      const position=hasHeader && headerPosition>=0 && headerPosition!==headerSlot ? parts[headerPosition] : '';
      const team=hasHeader && headerTeam>=0 ? parts[headerTeam] : '';
      if(position && !/^(QB|RB|WR|TE|K|DST|DEF|RB-WR-TE)$/i.test(position))throw Error('Invalid player position.');
      if(team && !/^[A-Z]{2,3}$/.test(team))throw Error('Invalid team abbreviation.');
      return {slot, player, status,...(position ? {position} : {}),...(team ? {team} : {})};
    });
  }
  function parseCSV(text) {
    const rows=[];let row=[],cell='',quoted=false;
    for(let i=0;i<text.length;i++) {
      const c=text[i];
      if(c==='"') {if(quoted && text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}
      else if(c===',' && !quoted){row.push(cell);cell='';}
      else if((c==='\n' || c==='\r') && !quoted){if(c==='\r' && text[i+1]==='\n')i++;row.push(cell);rows.push(row);row=[];cell='';}
      else cell+=c;
    }
    if(quoted) throw new Error('The CSV has an unfinished quoted field. Export the roster again.');
    if(cell || row.length){row.push(cell);rows.push(row);}return rows;
  }
  function parseCBS(rows,header) {
    const labels=rows[header].map(v=>v.trim().toLowerCase()),pos=labels.indexOf('pos'),name=labels.indexOf('players');
    let bench=false, totalsSeen=false;const result=[];
    for(const row of rows.slice(header+1)) {
      const text=row.join(' ').trim();if(!text)continue;
      if(totalsSeen)throw Error('Unexpected data after CBS roster totals. Export the full roster again.');
      if(/^reserves$/i.test(text)){bench=true;continue;}
      if(/^active:\s*\d+\s+reserve:\s*\d+$/i.test(text)) {
        totalsSeen=true;
        const totals=text.match(/active:\s*(\d+)\s+reserve:\s*(\d+)/i);
        if(result.filter(p=>p.slot!=='BN').length!==+totals[1] || result.filter(p=>p.slot==='BN').length!==+totals[2]) throw Error('CBS roster counts do not match the export. Import the full file again.');
        continue;
      }
      const position=(row[pos] || '').trim().toUpperCase(),raw=(row[name] || '').trim();
      if(!position || !raw || !/^(QB|RB|WR|TE|K|DST|DEF|RB-WR-TE)$/.test(position)) throw Error('Unrecognized CBS roster row. Export the roster overview again.');
      const identity=raw.match(/\s+(QB|RB|WR|TE|K|DST|DEF)\s*\|\s*([A-Z]{2,3})\s*$/);
      const player=identity ? raw.slice(0,identity.index).trim() : raw;
      if(!player || player.length>80)throw Error('Invalid CBS player name.');
      result.push({slot:bench ? 'BN' : position==='RB-WR-TE' ? 'FLEX' : position==='DST' ? 'DEF' : position,
        player,status:'Unknown',position:identity ? identity[1] : position,...(identity ? {team:identity[2]} : {})});
    }
    if(!totalsSeen)throw Error('CBS export is incomplete: missing roster totals. Export the full roster again.');
    if(new Set(result.map(p=>p.player.toLowerCase())).size!==result.length)throw Error('CBS export contains duplicate players. Check the roster before importing.');
    if(!result.length || result.length>80)throw Error('No complete CBS roster found.');
    return result;
  }
  function leagueUrl(value) {
    if (!value.trim()) return "";
    let url;
    try { url = new URL(value.trim()); } catch { throw new Error("Enter a complete league page URL."); }
    if (url.protocol !== "https:") throw new Error("Use an https league page URL.");
    return url.href;
  }
  const api = {parseRoster, leagueUrl};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RosterImport = api;
})(typeof window !== "undefined" ? window : globalThis);
