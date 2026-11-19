import React, { useState } from "react";
export function ProfileForm({api,name,onSaved}:{api:(path:string,options?:RequestInit)=>Promise<Response>,name:string,onSaved:()=>void}){
 const [value,setValue]=useState(name),[busy,setBusy]=useState(false),[error,setError]=useState("");
 return <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{const r=await api("/profile",{method:"PUT",body:JSON.stringify({name:value.trim()})});if(!r.ok)throw Error("Could not save your name.");onSaved();}catch(e){setError(e instanceof Error?e.message:"Could not save your name.");}finally{setBusy(false);}}}><label>What should Bujji call you?<input aria-label="Preferred name" maxLength={40} required value={value} onChange={e=>setValue(e.target.value)} autoComplete="given-name"/></label><button className="primary" type="submit" disabled={busy}>{busy?"Saving…":"Save name"}</button>{error&&<p role="alert">{error}</p>}</form>;
}
