/* Roster snapshots: parse explicit columns, never guess a player's identity. */
(function (root) {
  const statuses = {active:"Active", healthy:"Active", q:"Questionable", questionable:"Questionable",
    d:"Doubtful", doubtful:"Doubtful", o:"Out", out:"Out", ir:"IR", pup:"PUP", sus:"Sus",
    bye:"Bye", empty:"Empty", unknown:"Unknown", "":"Unknown"};
  function parseRoster(text, required = true) {
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    if (required && !lines.length) throw new Error("Paste a roster before saving.");
    if (!lines.length) return [];
    const split = line => line.split(line.includes("\t") ? "\t" : "|").map(value => value.trim());
    const first = split(lines[0]).map(value => value.toLowerCase());
    const headerPlayer = first.findIndex(value => ["player", "name", "player name"].includes(value));
    const headerSlot = first.findIndex(value => ["slot", "position", "pos"].includes(value));
    const headerStatus = first.findIndex(value => ["status", "injury", "injury status"].includes(value));
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
      return {slot, player, status};
    });
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
