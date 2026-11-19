import React, { useState } from 'react';
type Api = (path:string, options?:RequestInit)=>Promise<Response>;
export function DevicePairing({api}:{api:Api}) {
 const [code,setCode]=useState(''),[devices,setDevices]=useState<any[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();}catch(e){setError(e instanceof Error?e.message:'Device request failed');}finally{setBusy(false);}}
 async function changeGrant(d:any,capability:string,enabled:boolean){const remote={...d.remote,[capability]:enabled};setDevices(current=>current.map(item=>item.id===d.id?{...item,remote}:item));await run(async()=>{try{await api('/devices/'+encodeURIComponent(d.id)+'/access',{method:'PUT',body:JSON.stringify(remote)});await refresh();}catch(e){try{await refresh();}catch{}throw e;}});}
 async function refresh(){setDevices(await (await api('/devices')).json());}
 return <section className="desktop-settings">
  <h3>Connect your phone</h3>
  <p className="helper">Sync memories/reminders, and optionally enable phone control and read-only laptop files.</p>
  <details className="device-help"><summary>Setup</summary><p className="helper">Connect both devices to the same tailnet. With Bujji running, use PowerShell: <code>tailscale serve --bg http://127.0.0.1:8765</code>. Use your configured port if changed. Enter the HTTPS .ts.net address and pairing code in Android Settings. Never use Funnel or public port forwarding. Pairing starts with sync only. Enable the separate control/files switches below for your own phone.</p></details>
  <div className="device-actions"><button className="primary" disabled={busy} onClick={()=>run(async()=>{const r=await (await api('/devices/pairing',{method:'POST'})).json();setCode(r.code);await refresh();})}>Generate phone pairing code</button><button className="secondary" disabled={busy} onClick={()=>run(refresh)}>Refresh connected devices</button></div>
  {code&&<p className="helper">One-use code (10 minutes): <strong className="pairing-code">{code}</strong></p>}
  {devices.map(d=><div className="paired-device" key={d.id}><span>{d.name}</span><label><input type="checkbox" disabled={busy} checked={!!d.remote?.control} onChange={e=>changeGrant(d,'control',e.currentTarget.checked)}/> Phone control</label><label><input type="checkbox" disabled={busy} checked={!!d.remote?.files} onChange={e=>changeGrant(d,'files',e.currentTarget.checked)}/> Browse/download files</label><button className="secondary" disabled={busy} onClick={()=>run(async()=>{await api('/devices/'+encodeURIComponent(d.id),{method:'DELETE'});await refresh();})}>Revoke</button></div>)}
  {error&&<p role="alert">{error}</p>}
 </section>;
}
