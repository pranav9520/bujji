'use strict';
const {contextBridge,ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('bujjiDesktop', {
  chooseDocumentFolder: () => ipcRenderer.invoke('bujji:choose-document-folder'),
  openSettingsFolder: () => ipcRenderer.invoke('bujji:open-settings-folder'),
  openComputer: () => ipcRenderer.invoke('bujji:open-computer'),
  closeComputer: () => ipcRenderer.invoke('bujji:close-computer'),
  computer: (request) => ipcRenderer.invoke('bujji:computer',request),
  bootstrap: () => ipcRenderer.invoke('bujji:bootstrap'),
  preferences: () => ipcRenderer.invoke('bujji:preferences'),
  setPreferences: (value) => ipcRenderer.invoke('bujji:set-preferences',value),
  testSound: () => ipcRenderer.invoke('bujji:test-sound'),
  testNotification: () => ipcRenderer.invoke('bujji:test-notification'),
  onHidden: (callback) => {
    const listener = () => callback();
    ipcRenderer.on('bujji:hidden',listener);
    return () => ipcRenderer.removeListener('bujji:hidden',listener);
  },
});
