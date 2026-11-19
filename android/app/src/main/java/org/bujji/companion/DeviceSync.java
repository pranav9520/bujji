package org.bujji.companion;
import android.content.Context;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

/** Tailnet HTTPS only. Remote files/control require separate laptop-side per-phone grants. */
final class DeviceSync {
 private final Context context;private final Store store;private final SecretVault vault;private final AtomicBoolean busy=new AtomicBoolean();
 DeviceSync(Context c,Store s,SecretVault v){context=c;store=s;vault=v;}
 static String origin(String input){
  try{URI u=new URI(input.trim());String host=u.getHost();if(!"https".equals(u.getScheme())||host==null||!host.toLowerCase(java.util.Locale.ROOT).endsWith(".ts.net")||u.getRawUserInfo()!=null||(u.getPort()!=-1&&u.getPort()!=443)||u.getRawQuery()!=null||u.getRawFragment()!=null||!(u.getRawPath()==null||u.getRawPath().isEmpty()||u.getRawPath().equals("/")))throw new IllegalArgumentException();return "https://"+host.toLowerCase(java.util.Locale.ROOT);}
  catch(Exception e){throw new IllegalArgumentException("Use your laptop's HTTPS .ts.net address from Tailscale Serve, without a path, port or token.");}
 }
 private volatile HttpURLConnection controlConnection;
 void cancelControl(){HttpURLConnection c=controlConnection;if(c!=null)c.disconnect();}
 private JSONObject request(String base,String path,JSONObject body,boolean auth) throws Exception {
  HttpURLConnection c=(HttpURLConnection)new URL(origin(base)+"/api/devices/"+path).openConnection();c.setConnectTimeout(10000);c.setReadTimeout(path.equals("remote/chat")?110000:path.equals("remote/control")?90000:25000);c.setInstanceFollowRedirects(false);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");if(auth)c.setRequestProperty("Authorization","Bearer "+vault.get("laptop"));
  boolean control=path.equals("remote/chat")||(path.equals("remote/control")&&!body.optString("operation").equals("stop"));if(control)controlConnection=c;
  try{try(OutputStream out=c.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}int code=c.getResponseCode();if(code==401)throw new IOException("The laptop revoked or rejected this phone. Pair it again.");if(code==403)throw new IOException(path.startsWith("remote/")?"Enable phone control/files in laptop Devices first.":"Pairing code expired, locked or incorrect. Generate another on the laptop.");if(code==404)throw new IOException("Update both devices to compatible community builds; this laptop server lacks the requested feature.");if(code<200||code>=300){String detail="";try{detail=new JSONObject(new String(Cloud.read(c.getErrorStream(),8192),StandardCharsets.UTF_8)).optString("detail");}catch(Exception ignored){}throw new IOException(detail.length()>0&&detail.length()<1000?detail:"Laptop request did not finish (HTTP "+code+"). Check the laptop before retrying.");}return new JSONObject(new String(Cloud.read(c.getInputStream(),2_500_000),StandardCharsets.UTF_8));}
  catch(java.net.SocketTimeoutException e){throw new IOException("Laptop connection timed out. Keep Bujji running and connect both devices to Tailscale.");}catch(javax.net.ssl.SSLException e){throw new IOException("The laptop HTTPS certificate could not be verified. Check Tailscale Serve; insecure certificates are never accepted.");}catch(java.net.UnknownHostException|java.net.ConnectException e){throw new IOException("Laptop unreachable. Check that both devices are online in the same Tailscale network and Bujji is running.");}finally{c.disconnect();if(controlConnection==c)controlConnection=null;}
 }
 JSONObject remote(String path,JSONObject body) throws Exception {
  if(!java.util.Arrays.asList("status","files","control","chat").contains(path))throw new IllegalArgumentException("Unsupported laptop request");
  JSONObject p=store.meta("pairing",new JSONObject());if(!vault.has("laptop")||!p.has("url"))throw new IllegalArgumentException("Pair your laptop in Settings first.");
  return request(p.getString("url"),"remote/"+path,body,true);
 }
 static String filename(String path){String name=path.replace('\\','/');name=name.substring(name.lastIndexOf('/')+1);if(name.isEmpty()||name.equals(".")||name.equals("..")||name.length()>240||name.indexOf('\n')>=0||name.indexOf('\r')>=0)throw new IllegalArgumentException("Select a valid filename.");return name;}
 JSONObject saveDownload(String path) throws Exception {
  if(android.os.Build.VERSION.SDK_INT<29)throw new IOException("This Android version needs the Save as file picker.");
  String name=filename(path),extension=name.contains(".")?name.substring(name.lastIndexOf('.')+1).toLowerCase(java.util.Locale.ROOT):"";String mime=android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
  android.content.ContentValues values=new android.content.ContentValues();values.put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME,name);values.put(android.provider.MediaStore.MediaColumns.MIME_TYPE,mime==null?"application/octet-stream":mime);values.put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH,android.os.Environment.DIRECTORY_DOWNLOADS+"/Bujji/");values.put(android.provider.MediaStore.MediaColumns.IS_PENDING,1);
  android.net.Uri uri=context.getContentResolver().insert(android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);if(uri==null)throw new IOException("Could not create a file in Downloads.");
  try{download(path,uri);android.content.ContentValues ready=new android.content.ContentValues();ready.put(android.provider.MediaStore.MediaColumns.IS_PENDING,0);if(context.getContentResolver().update(uri,ready,null,null)<1)throw new IOException("Could not finish saving the downloaded file.");try{store.markFileSaved(path);}catch(Exception ignored){}try(android.database.Cursor row=context.getContentResolver().query(uri,new String[]{android.provider.MediaStore.MediaColumns.DISPLAY_NAME},null,null,null)){if(row!=null&&row.moveToFirst())name=row.getString(0);}catch(Exception ignored){}return new JSONObject().put("message","Saved to Downloads/Bujji: "+name).put("saved",true);}
  catch(Exception e){try{context.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}throw e;}
 }
 void download(String path,android.net.Uri destination) throws Exception {
  JSONObject p=store.meta("pairing",new JSONObject());if(!vault.has("laptop")||!p.has("url"))throw new IllegalArgumentException("Pair your laptop first.");
  HttpURLConnection c=(HttpURLConnection)new URL(origin(p.getString("url"))+"/api/devices/remote/files").openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(90000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setRequestProperty("Authorization","Bearer "+vault.get("laptop"));
  try{try(OutputStream out=c.getOutputStream()){out.write(new JSONObject().put("operation","download").put("path",path).toString().getBytes(StandardCharsets.UTF_8));}int code=c.getResponseCode();if(code!=200)throw new IOException(code==403?"Enable file access for this phone in laptop Devices.":"Download failed (HTTP "+code+"). File must be available and at most 25 MB.");long declared=c.getContentLengthLong();if(declared>25*1024*1024)throw new IOException("File exceeds 25 MB.");try(InputStream in=c.getInputStream();OutputStream out=context.getContentResolver().openOutputStream(destination)){if(out==null)throw new IOException("Could not open the chosen destination.");copyDownload(in,out,declared);}}
  catch(Exception e){try{android.provider.DocumentsContract.deleteDocument(context.getContentResolver(),destination);}catch(Exception ignored){}throw e;}finally{c.disconnect();}
 }
 static void copyDownload(InputStream in,OutputStream out,long declared) throws IOException {
  if(declared>25*1024*1024)throw new IOException("File exceeds 25 MB.");byte[] chunk=new byte[16384];long count=0;int n;while((n=in.read(chunk))!=-1){count+=n;if(count>25*1024*1024)throw new IOException("File exceeds 25 MB.");out.write(chunk,0,n);}if(declared>=0&&count!=declared)throw new IOException("Incomplete download. Please try again.");
 }
 JSONObject pair(JSONObject p) throws Exception {
  if(!p.optBoolean("confirmed"))throw new IllegalArgumentException("Confirm sharing saved memories and reminders first.");if(!busy.compareAndSet(false,true))throw new IllegalArgumentException("A device request is already running.");
  try{String url=origin(p.getString("url"));String code=p.getString("code").trim().toLowerCase(java.util.Locale.ROOT);if(!code.matches("[a-f0-9]{16}"))throw new IllegalArgumentException("Paste the 16-character pairing code from laptop Settings.");JSONObject r=request(url,"pair",new JSONObject().put("code",code).put("name",Rules.bounded(p.optString("name","Android phone"),40)),false);if(r.optInt("protocol")!=1||r.optString("token").length()<32)throw new IllegalArgumentException("Unexpected laptop pairing response.");
   JSONObject old=store.meta("syncOrigin",store.meta("pairing",new JSONObject()));vault.save("laptop",r.getString("token"));if(!url.equals(old.optString("url")))store.clearSyncLinks();store.putMeta("syncOrigin",new JSONObject().put("url",url));store.putMeta("pairing",new JSONObject().put("url",url).put("device",r.getString("id")).put("lastSync",0));return new JSONObject().put("message","Paired. Tap Sync now to exchange saved memories and reminders.");
  }finally{busy.set(false);}
 }
 JSONObject sync() throws Exception {
  if(!busy.compareAndSet(false,true))throw new IllegalArgumentException("A device request is already running.");
  try{JSONObject pairing=store.meta("pairing",new JSONObject());if(!vault.has("laptop")||!pairing.has("url"))throw new IllegalArgumentException("Pair with your laptop first.");JSONObject snapshot=store.syncSnapshot();JSONObject response=request(pairing.getString("url"),"sync",new JSONObject().put("changes",snapshot.getJSONArray("changes")),true);
   // Cancel old alarms before merging due times/cancellations; recreate from the committed data.
   org.json.JSONArray old=store.pending();for(int i=0;i<old.length();i++)Reminders.cancel(context,old.getJSONObject(i));int conflicts;
   try{conflicts=store.mergeSync(response,snapshot);}finally{Reminders.recover(context,store);}
   pairing.put("lastSync",System.currentTimeMillis());store.putMeta("pairing",pairing);
   return new JSONObject().put("message","Memories and reminders synced."+(conflicts>0?" "+conflicts+" conflicting phone version(s) saved in Sync recovery; laptop versions kept.":"")).put("conflicts",conflicts);
  }finally{busy.set(false);}
 }
 void disconnect(){cancelControl();if(!busy.compareAndSet(false,true))throw new IllegalArgumentException("Wait for the device request to finish before disconnecting.");try{vault.clear("laptop");store.putMeta("pairing",new JSONObject());}finally{busy.set(false);}/* Keep data and ID links for safe re-pairing to the same laptop. */}
 JSONObject status() throws JSONException {JSONObject p=store.meta("pairing",new JSONObject());return new JSONObject(p.toString()).put("paired",vault.has("laptop")&&p.has("url")).put("conflicts",store.rows("SELECT kind,body,created FROM mobile_conflicts ORDER BY created DESC LIMIT 20"));}
}
