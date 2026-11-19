package org.bujji.companion;
import android.content.Context;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.json.*;
import java.time.*;
import java.util.TimeZone;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class DeepWorkTest {
 private Store store;private Context context;private DeepWork work;private TimeZone oldZone;private final long at=Instant.parse("2026-11-18T10:00:00Z").toEpochMilli();
 @Before public void open(){oldZone=TimeZone.getDefault();TimeZone.setDefault(TimeZone.getTimeZone("Asia/Kolkata"));context=RuntimeEnvironment.getApplication();context.deleteDatabase("bujji-mobile.sqlite3");store=new Store(context);work=new DeepWork(store);}
 @After public void close(){store.close();context.deleteDatabase("bujji-mobile.sqlite3");TimeZone.setDefault(oldZone);}
 private JSONObject act(String action,long now) throws Exception {return work.action(new JSONObject().put("action",action),now);}
 private void start(int rounds,boolean auto) throws Exception {work.action(new JSONObject().put("action","start").put("title","Study").put("work_minutes",1).put("break_minutes",1).put("rounds",rounds).put("auto_break",auto),at);}
 @Test public void pauseResumeExcludesPausedMinutes() throws Exception {start(1,true);assertEquals(40000,act("pause",at+20000).getJSONObject("active").getLong("remaining"));assertEquals(20000,work.snapshot(at+300000).getJSONObject("stats").getLong("focused_ms"));act("resume",at+300000);JSONObject d=work.snapshot(at+340000);assertEquals("finished",d.getJSONObject("active").getString("status"));assertEquals(60000,d.getJSONObject("stats").getLong("focused_ms"));assertEquals(1,d.getJSONObject("stats").getInt("completed"));}
 @Test public void restartAndOfflineGapDoNotCreditUnstartedSessions() throws Exception {start(3,true);store.close();store=new Store(context);work=new DeepWork(store);JSONObject d=work.snapshot(at+600000),s=d.getJSONObject("active");assertEquals("ready",s.getString("status"));assertEquals("work",s.getString("phase"));assertEquals(2,s.getInt("round"));assertEquals(60000,d.getJSONObject("stats").getLong("focused_ms"));assertEquals(1,d.getJSONObject("stats").getInt("completed"));assertEquals(2,store.rows("SELECT * FROM focus_signals").length());work.snapshot(at+700000);assertEquals(2,store.rows("SELECT * FROM focus_signals").length());}
 @Test public void manualBreakWaitsUntilStarted() throws Exception {start(2,false);JSONObject s=work.snapshot(at+60000).getJSONObject("active");assertEquals("break",s.getString("phase"));assertEquals("ready",s.getString("status"));s=act("resume",at+300000).getJSONObject("active");assertEquals(at+360000,s.getLong("deadline"));assertEquals("ready",work.snapshot(at+360000).getJSONObject("active").getString("status"));}
 @Test public void resetAndEndKeepRecordedTime() throws Exception {start(2,true);act("reset",at+10000);act("resume",at+20000);JSONObject stats=act("end",at+30000).getJSONObject("stats");assertEquals(20000,stats.getLong("focused_ms"));assertEquals(0,stats.getInt("completed"));assertEquals(0,stats.getInt("completion"));}
 @Test public void tasksAndHistorySurviveBackupWithoutResumingTimers() throws Exception {JSONObject d=work.action(new JSONObject().put("action","task_add").put("title","DBMS"),at);String id=d.getJSONArray("tasks").getJSONObject(0).getString("id");work.action(new JSONObject().put("action","task_toggle").put("task_id",id).put("done",true),at);start(1,true);work.snapshot(at+60000);JSONObject backup=store.backup();assertEquals(1,backup.getJSONObject("data").getJSONArray("focus_tasks").length());assertEquals(1,backup.getJSONObject("data").getJSONArray("focus_history").length());assertFalse(backup.toString().contains("deep_focus"));store.restore(backup);assertEquals(1,store.rows("SELECT * FROM focus_history").length());}
 @Test public void databaseV2UpgradeKeepsChatsAndAddsFocusTables(){store.message("user","Before update","phone");store.getWritableDatabase().execSQL("DROP TABLE focus_tasks");store.getWritableDatabase().execSQL("DROP TABLE focus_history");store.getWritableDatabase().execSQL("DROP TABLE focus_signals");store.getWritableDatabase().setVersion(2);store.close();store=new Store(context);assertEquals(1,store.messages().length());assertEquals(0,store.rows("SELECT * FROM focus_tasks").length());}
 @Test public void crossingMidnightSplitsTimerTime() throws Exception {long start=Instant.parse("2026-11-18T18:25:00Z").toEpochMilli();work.action(new JSONObject().put("action","start").put("title","Night").put("work_minutes",10).put("rounds",1),start);JSONObject stats=work.snapshot(start+600000).getJSONObject("stats");assertEquals(300000,stats.getLong("focused_ms"));assertEquals(1,stats.getInt("completed"));}
 @Test public void newStartCannotOverwriteActiveTimer() throws Exception {start(1,true);try{start(1,true);fail("Replaced active timer");}catch(IllegalArgumentException expected){}assertEquals("Study",work.active().optString("title"));}

 @Test public void quietBujjiKeepsRegularReminderInHistory() throws Exception {
  long now=System.currentTimeMillis();work.action(new JSONObject().put("action","start").put("title","Quiet study").put("work_minutes",10).put("quiet",true),now);
  JSONObject r=store.addReminder("Quiet reminder",now+10000,"none","reminder");android.content.ContentValues values=new android.content.ContentValues();values.put("due",now-1000);store.getWritableDatabase().update("reminders",values,"id=?",new String[]{r.getString("id")});Reminders.fire(context,store,r.getString("id"));assertEquals("quiet_history",store.rows("SELECT outcome FROM events WHERE reminder_id=?",r.getString("id")).getJSONObject(0).getString("outcome"));assertEquals(0,context.getSystemService(android.app.NotificationManager.class).getActiveNotifications().length);
 }
}
