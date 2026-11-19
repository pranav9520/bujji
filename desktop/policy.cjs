'use strict';
const path = require('node:path');
const APPROVED = new Set(['bujji:open-settings-folder','bujji:choose-document-folder','bujji:bootstrap','bujji:preferences','bujji:set-preferences','bujji:test-notification','bujji:test-sound','bujji:open-computer','bujji:close-computer','bujji:computer']);
function isLocalFrame(url, origin) {
  try { return new URL(url).origin === origin; } catch { return false; }
}
function validIPC(event, window, origin, channel) {
  return APPROVED.has(channel) && !!window && !window.isDestroyed() && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame && isLocalFrame(event.senderFrame.url,origin);
}
function validComputerIPC(event,window,origin,channel) { return ['bujji:computer','bujji:close-computer'].includes(channel) && validIPC(event,window,origin,channel) && window.isVisible(); }
function preferences(value={}) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid preferences');
  if (Object.keys(value).some(key => !['soundEnabled','startAtLogin'].includes(key))) throw new Error('Unknown preference');
  for (const v of Object.values(value)) if (typeof v !== 'boolean') throw new Error('Expected a boolean preference');
  return {...value};
}
function localDirectory(root, configured, fallback) { return path.resolve(root, configured || fallback); }
function desktopPort(value) { const number = value === undefined ? 8765 : Number(value); if (!Number.isInteger(number) || number < 1024 || number > 65535) throw new Error('Invalid BUJJI_DESKTOP_PORT'); return number; }
function readyLine(line, expected) {
  if (!line.startsWith('BUJJI_READY:')) return false;
  try {return JSON.parse(line.slice('BUJJI_READY:'.length)).port === expected;} catch {return false;}
}
module.exports = {isLocalFrame,validIPC,validComputerIPC,preferences,localDirectory,desktopPort,readyLine};
