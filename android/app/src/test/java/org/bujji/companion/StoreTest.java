package org.bujji.companion;
import android.content.Context;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.json.*;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class StoreTest {
 private Store store;private Context context;
 @Before public void open(){context=RuntimeEnvironment.getApplication();context.deleteDatabase("bujji-mobile.sqlite3");store=new Store(context);}
 @After public void close(){store.close();context.deleteDatabase("bujji-mobile.sqlite3");}
 @Test public void restartPreservesChatMemoryAndPendingReminder() throws Exception {
  store.message("user","Continue my project","phone");store.addMemory("Project Bujji");String id=store.addReminder("Study",System.currentTimeMillis()+60000,"none","reminder").getString("id");store.close();store=new Store(context);
  assertEquals("Continue my project",store.messages().getJSONObject(0).getString("body"));assertEquals(1,store.memories().length());assertEquals("pending",store.reminder(id).getString("status"));
 }
 @Test public void duplicateDueBroadcastClaimsOnlyOnce() throws Exception {
  long at=System.currentTimeMillis()+60000;String id=store.addReminder("Study",at,"none","reminder").getString("id");assertNotNull(store.claim(id,at,false));assertNull(store.claim(id,at,false));assertEquals(1,store.rows("SELECT * FROM events").length());assertEquals("done",store.reminder(id).getString("status"));
 }
 @Test public void recurringReminderAdvancesAndDoesNotFireEarly() throws Exception {
  long at=System.currentTimeMillis()+60000;String id=store.addReminder("Study",at,"daily","reminder").getString("id");assertNull(store.claim(id,at-5000,false));assertNotNull(store.claim(id,at,false));assertTrue(store.reminder(id).getLong("due")>at);assertNull(store.claim(id,at,false));
 }
 @Test public void forgottenMemoryIsTombstonedAndNotUsedAsContext() throws Exception {store.addMemory("Private preference");String id=store.memories().getJSONObject(0).getString("id");store.removeMemory(id);assertEquals(0,store.memories().length());assertEquals(1,store.rows("SELECT * FROM memories WHERE deleted=1").length());}
 @Test public void backupMergeDeduplicatesAndExcludesKeysAndSettings() throws Exception {
  store.message("user","Hi","phone");store.addMemory("Remembered");store.putMeta("settings",new JSONObject().put("name","Alex"));JSONObject backup=store.backup();assertFalse(backup.toString().contains("settings"));assertFalse(backup.toString().contains("apiKey"));store.restore(backup);assertEquals(1,store.messages().length());assertEquals(1,store.memories().length());
 }
 @Test public void invalidImportRollsBackAllRows() throws Exception {
  store.addMemory("Existing");JSONObject backup=store.backup();JSONObject good=backup.getJSONObject("data").getJSONArray("memories").getJSONObject(0);good.put("id",java.util.UUID.randomUUID().toString());backup.getJSONObject("data").getJSONArray("memories").put(new JSONObject(good.toString()).put("id","invalid"));
  try{store.restore(backup);fail("Invalid backup accepted");}catch(IllegalArgumentException expected){}assertEquals(1,store.memories().length());
 }
 @Test public void cancelledRemindersStayCancelledAcrossRestart() throws Exception {String id=store.addReminder("Cancelled",System.currentTimeMillis()+60000,"none","reminder").getString("id");store.cancel(id);store.close();store=new Store(context);assertEquals(0,store.pending().length());assertNull(store.claim(id,System.currentTimeMillis()+120000,false));}

 @Test public void modelCannotProposeAnUnsupportedDeviceAction() throws Exception {
  try{Cloud.parse(new JSONObject().put("type","shell").put("command","anything"));fail("Unsupported action accepted");}catch(IllegalArgumentException expected){}
 }
 @Test public void modelActionIsOnlyAValidatedPlan() throws Exception {
  Rules.Plan plan=Cloud.parse(new JSONObject().put("type","memory").put("text","I like concise replies"));assertEquals("memory",plan.type);assertEquals(0,store.memories().length());
 }
 @Test public void modelPastReminderRejected() throws Exception {
  try{Cloud.parse(new JSONObject().put("type","reminder").put("title","Past").put("at","2020-01-01T05:00:00+05:30"));fail("Past action accepted");}catch(IllegalArgumentException expected){}
 }
 @Test public void existingOccurrenceLedgerStillAdvancesPendingRow() throws Exception {
  long at=System.currentTimeMillis()+60000;String id=store.addReminder("Already delivered",at,"daily","reminder").getString("id");android.content.ContentValues v=new android.content.ContentValues();v.put("reminder_id",id);v.put("due",at);v.put("title","Already delivered");v.put("outcome","notified");v.put("created",at);store.getWritableDatabase().insertOrThrow("events",null,v);
  assertNull(store.claim(id,at,false));assertTrue(store.reminder(id).getLong("due")>at);assertEquals(1,store.rows("SELECT * FROM events").length());
 }

 private JSONObject shared(String id,String body,boolean deleted,long revision) throws Exception {return new JSONObject().put("id",id).put("kind","memory").put("revision",revision).put("payload",new JSONObject().put("body",body).put("deleted",deleted));}
 private JSONObject syncReply(JSONObject row,JSONArray results) throws Exception {return new JSONObject().put("protocol",1).put("records",new JSONArray().put(row)).put("results",results);}
 @Test public void syncImportIsIdempotentAndForgetPropagates() throws Exception {
  String id=java.util.UUID.randomUUID().toString();store.mergeSync(syncReply(shared(id,"Laptop context",false,1),new JSONArray()),store.syncSnapshot());assertEquals(1,store.memories().length());assertEquals(0,store.syncSnapshot().getJSONArray("changes").length());
  store.mergeSync(syncReply(shared(id,"Laptop context",false,1),new JSONArray()),store.syncSnapshot());assertEquals(1,store.memories().length());store.removeMemory(id);JSONObject change=store.syncSnapshot().getJSONArray("changes").getJSONObject(0);assertEquals(1,change.getInt("revision"));assertTrue(change.getBoolean("deleted"));
 }
 @Test public void conflictingPhoneEditIsKeptInRecovery() throws Exception {
  String id=java.util.UUID.randomUUID().toString();store.mergeSync(syncReply(shared(id,"Original",false,1),new JSONArray()),store.syncSnapshot());android.content.ContentValues v=new android.content.ContentValues();v.put("body","Offline phone version");store.getWritableDatabase().update("memories",v,"id=?",new String[]{id});JSONObject snapshot=store.syncSnapshot();
  int conflicts=store.mergeSync(syncReply(shared(id,"Laptop version",false,2),new JSONArray().put(new JSONObject().put("id",id).put("status","conflict"))),snapshot);
  assertEquals(1,conflicts);assertEquals("Laptop version",store.memories().getJSONObject(0).getString("body"));assertTrue(store.rows("SELECT * FROM mobile_conflicts").getJSONObject(0).getString("body").contains("Offline phone version"));assertEquals(0,store.syncSnapshot().getJSONArray("changes").length());
 }
 @Test public void editDuringSyncRemainsPendingInsteadOfBeingOverwritten() throws Exception {
  String id=java.util.UUID.randomUUID().toString();store.mergeSync(syncReply(shared(id,"Original",false,1),new JSONArray()),store.syncSnapshot());JSONObject snapshot=store.syncSnapshot();android.content.ContentValues v=new android.content.ContentValues();v.put("body","Typed while syncing");store.getWritableDatabase().update("memories",v,"id=?",new String[]{id});
  store.mergeSync(syncReply(shared(id,"Server version",false,2),new JSONArray()),snapshot);assertEquals("Typed while syncing",store.memories().getJSONObject(0).getString("body"));assertEquals(2,store.syncSnapshot().getJSONArray("changes").getJSONObject(0).getInt("revision"));
 }
 @Test public void phoneUploadLinksToItsOriginalId() throws Exception {
  store.addMemory("Phone fact");String id=store.memories().getJSONObject(0).getString("id");JSONObject snapshot=store.syncSnapshot();store.mergeSync(syncReply(shared(id,"Phone fact",false,3),new JSONArray().put(new JSONObject().put("id",id).put("status","applied"))),snapshot);assertEquals(1,store.memories().length());assertEquals(0,store.syncSnapshot().getJSONArray("changes").length());
 }
 @Test public void deletingLaptopMemoryCreatesPhoneTombstone() throws Exception {
  String id=java.util.UUID.randomUUID().toString();store.mergeSync(syncReply(shared(id,"Old fact",false,1),new JSONArray()),store.syncSnapshot());store.mergeSync(syncReply(shared(id,"Old fact",true,2),new JSONArray()),store.syncSnapshot());assertEquals(0,store.memories().length());assertEquals(0,store.syncSnapshot().getJSONArray("changes").length());
 }
 @Test public void v1UpgradePreservesExistingData() throws Exception {
  store.addMemory("Before upgrade");store.getWritableDatabase().execSQL("DROP TABLE mobile_links");store.getWritableDatabase().execSQL("DROP TABLE mobile_conflicts");store.getWritableDatabase().setVersion(1);store.close();store=new Store(context);assertEquals("Before upgrade",store.memories().getJSONObject(0).getString("body"));assertEquals(1,store.syncSnapshot().getJSONArray("changes").length());
 }
 @Test public void pairingUrlRequiresPrivateTailnetHttps(){assertEquals("https://laptop.tailnet.ts.net",DeviceSync.origin("https://laptop.tailnet.ts.net/"));for(String url:new String[]{"http://laptop.tailnet.ts.net","https://evil.com","https://laptop.tailnet.ts.net.evil.com","https://name:token@laptop.tailnet.ts.net","https://laptop.tailnet.ts.net/?token=x","https://laptop.tailnet.ts.net:8000"}){try{DeviceSync.origin(url);fail("Unsafe origin accepted: "+url);}catch(IllegalArgumentException expected){}}}

 @Test public void sharedReminderUpdatesDueAndCancellationWithoutChangingAlarmSlot() throws Exception {
  String id=java.util.UUID.randomUUID().toString();long due=System.currentTimeMillis()+3600000;JSONObject payload=new JSONObject().put("title","Shared study").put("due",due).put("repeat","daily").put("status","pending");JSONObject row=new JSONObject().put("id",id).put("kind","reminder").put("revision",1).put("payload",payload);
  store.mergeSync(syncReply(row,new JSONArray()),store.syncSnapshot());int slot=store.reminder(id).getInt("slot");assertEquals(0,store.syncSnapshot().getJSONArray("changes").length());
  payload.put("due",due+3600000).put("status","cancelled");row.put("revision",2);store.mergeSync(syncReply(row,new JSONArray()),store.syncSnapshot());assertEquals(slot,store.reminder(id).getInt("slot"));assertEquals("cancelled",store.reminder(id).getString("status"));assertEquals(due+3600000,store.reminder(id).getLong("due"));
 }
 @Test public void duplicateMemoryLinksToExistingLocalRecord() throws Exception {
  store.addMemory("Same fact");String local=store.memories().getJSONObject(0).getString("id"),remote=java.util.UUID.randomUUID().toString();JSONObject snapshot=store.syncSnapshot();JSONArray result=new JSONArray().put(new JSONObject().put("id",local).put("status","duplicate").put("remote_id",remote));store.mergeSync(syncReply(shared(remote,"Same fact",false,1),result),snapshot);assertEquals(1,store.memories().length());assertEquals(0,store.syncSnapshot().getJSONArray("changes").length());assertEquals(local,store.memories().getJSONObject(0).getString("id"));
 }
}
