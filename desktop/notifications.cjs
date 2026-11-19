'use strict';
// First connection establishes a baseline. Later polls never replay older IDs.
function notificationBatch(rows, cursor, soundEnabled) {
  const valid = rows.filter(n => Number.isSafeInteger(n.id) && n.id > 0 && typeof n.content === 'string');
  const highest = valid.reduce((max,n) => Math.max(max,n.id),0);
  if (cursor === null || highest < cursor) return {cursor:highest,toast:null};
  const fresh = valid.filter(n => n.id > cursor && !n.read && !n.quiet).sort((a,b) => a.id-b.id);
  if (!fresh.length) return {cursor:Math.max(cursor,highest),toast:null};
  const missed = fresh.every(n => n.content.startsWith('Missed while offline:'));
  const title = fresh.length === 1 ? 'Bujji reminder' : `Bujji · ${fresh.length} reminders`;
  const body = fresh.length === 1 ? fresh[0].content.slice(0,400) : `${fresh[0].content.slice(0,250)}\nOpen Bujji for all ${fresh.length} reminders.`;
  return {cursor:Math.max(cursor,highest),toast:{title,body,silent:!soundEnabled || missed}};
}
module.exports = {notificationBatch};
