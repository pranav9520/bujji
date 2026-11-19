package org.bujji.companion;
import android.app.*;
import android.content.*;
import android.database.sqlite.SQLiteDatabase;
import android.net.Uri;
import org.json.*;
import java.time.*;
import java.util.*;

/** Persistent elapsed-timer sessions, not an attention measurement. */
final class DeepWork {
 static final Object LOCK=new Object();private final Store store;
 DeepWork(Store s){store=s;}
 JSONObject active(){return store.meta("deep_focus",new JSONObject());}
 void save(JSONObject s){store.putMeta("deep_focus",s);}
 static boolean quiet(Store s){JSONObject a=s.meta("deep_focus",new JSONObject());return a.optString("status").equals("running")&&a.optString("phase").equals("work")&&a.optBoolean("quiet")&&System.currentTimeMillis()<a.optLong("deadline");}
 private void record(JSONObject s,String status,long at) throws Exception {
  if(!s.optString("phase").equals("work"))return;JSONArray segments=s.getJSONArray("segments");
  if(s.optString("status").equals("running")&&s.optLong("anchor")>0){long end=Math.min(at,s.getLong("deadline"));if(end>s.getLong("anchor"))segments.put(new JSONArray().put(s.getLong("anchor")).put(end));}
  s.put("anchor",0);
  if(segments.length()>0||status.equals("completed")){ContentValues v=new ContentValues();v.put("id",s.getString("id"));v.put("title",s.getString("title"));v.put("status",status);v.put("planned",s.getLong("work_ms"));v.put("ended",at);v.put("segments",segments.toString());v.put("task",s.optString("task_id"));store.getWritableDatabase().insertWithOnConflict("focus_history",null,v,SQLiteDatabase.CONFLICT_IGNORE);}
 }
 private void signal(String text,long at){ContentValues v=new ContentValues();v.put("body",text);v.put("created",at);v.put("delivered",0);store.getWritableDatabase().insertOrThrow("focus_signals",null,v);}
 private void next(JSONObject s) throws Exception {s.put("id",UUID.randomUUID().toString()).put("round",s.getInt("round")+1).put("phase","work").put("status","ready").put("remaining",s.getLong("work_ms")).put("deadline",0).put("anchor",0).put("segments",new JSONArray());}
 private void advanceIn(JSONObject s,long at) throws Exception {
  if(!s.optString("status").equals("running")||at<s.getLong("deadline"))return;long end=s.getLong("deadline");
  if(s.getString("phase").equals("work")){
   record(s,"completed",end);signal("Focus: "+s.getString("title")+" completed.",end);
   if(s.getInt("round")>=s.getInt("rounds"))s.put("status","finished").put("remaining",0).put("deadline",0);
   else if(s.getLong("break_ms")>0)s.put("phase","break").put("status",s.getBoolean("auto_break")?"running":"ready").put("remaining",s.getLong("break_ms")).put("deadline",s.getBoolean("auto_break")?end+s.getLong("break_ms"):0).put("anchor",0).put("segments",new JSONArray());
   else next(s);
  }
  if(s.getString("phase").equals("break")&&s.getString("status").equals("running")&&at>=s.getLong("deadline")){signal("Break: finished. Start your next session when ready.",s.getLong("deadline"));next(s);}
  save(s);
 }
 void advance(long at) throws Exception {synchronized(LOCK){SQLiteDatabase db=store.getWritableDatabase();db.beginTransaction();try{advanceIn(active(),at);db.setTransactionSuccessful();}finally{db.endTransaction();}}}
 JSONObject action(JSONObject p,long at) throws Exception {synchronized(LOCK){SQLiteDatabase db=store.getWritableDatabase();db.beginTransaction();try{
  JSONObject s=active();advanceIn(s,at);String a=p.getString("action");
  if(a.equals("task_add")){String title=Rules.bounded(p.optString("title"),200);if(store.rows("SELECT id FROM focus_tasks LIMIT 201").length()>=200)throw new IllegalArgumentException("Remove an old task first (200 maximum).");ContentValues v=new ContentValues();v.put("id",UUID.randomUUID().toString());v.put("title",title);v.put("done",0);v.put("created",at);db.insertOrThrow("focus_tasks",null,v);}
  else if(Arrays.asList("task_toggle","task_delete","task_select").contains(a)){
   String id=p.getString("task_id");JSONObject task=store.rows("SELECT * FROM focus_tasks WHERE id=?",id).optJSONObject(0);if(task==null)throw new IllegalArgumentException("Task not found.");
   if(a.equals("task_toggle")){ContentValues v=new ContentValues();v.put("done",p.optBoolean("done")?1:0);db.update("focus_tasks",v,"id=?",new String[]{id});}
   else if(a.equals("task_delete")){db.delete("focus_tasks","id=?",new String[]{id});if(store.meta("focus_choice",new JSONObject()).optString("task_id").equals(id))store.putMeta("focus_choice",new JSONObject());}
   else {if(Arrays.asList("running","paused").contains(s.optString("status")))throw new IllegalArgumentException("End the current session before choosing another task.");store.putMeta("focus_choice",new JSONObject().put("title",task.getString("title")).put("task_id",id));}
  }
  else if(a.equals("start")){
   if(Arrays.asList("running","paused","ready").contains(s.optString("status")))throw new IllegalArgumentException("End the current session first.");
   int work=p.optInt("work_minutes",45),pause=p.optInt("break_minutes",10),rounds=p.optInt("rounds",3);if(work<1||work>180||pause<0||pause>60||rounds<1||rounds>12)throw new IllegalArgumentException("Choose 1–180 work minutes, 0–60 break minutes and 1–12 sessions.");
   String task=p.optString("task_id","");if(!task.isEmpty()&&store.rows("SELECT id FROM focus_tasks WHERE id=?",task).length()==0)throw new IllegalArgumentException("Task not found.");
   s=new JSONObject().put("id",UUID.randomUUID().toString()).put("title",Rules.bounded(p.optString("title","Deep work"),200)).put("task_id",task).put("work_ms",work*60000L).put("break_ms",pause*60000L).put("rounds",rounds).put("round",1).put("phase","work").put("status","running").put("remaining",work*60000L).put("deadline",at+work*60000L).put("anchor",at).put("segments",new JSONArray()).put("quiet",p.optBoolean("quiet")).put("auto_break",p.optBoolean("auto_break",true));
   store.putMeta("focus_defaults",new JSONObject().put("work_minutes",work).put("break_minutes",pause).put("rounds",rounds).put("quiet",p.optBoolean("quiet")).put("auto_break",p.optBoolean("auto_break",true)));
  }
  else if(a.equals("settings")){if(s.has("id"))s.put("quiet",p.optBoolean("quiet")).put("auto_break",p.optBoolean("auto_break",true));JSONObject cfg=store.meta("focus_defaults",new JSONObject().put("work_minutes",45).put("break_minutes",10).put("rounds",3));cfg.put("quiet",p.optBoolean("quiet")).put("auto_break",p.optBoolean("auto_break",true));store.putMeta("focus_defaults",cfg);}
  else {
   if(!s.has("id"))throw new IllegalArgumentException("Start a focus session first.");
   switch(a){
    case "pause":if(!s.optString("status").equals("running"))break;if(s.getString("phase").equals("work")&&at>s.getLong("anchor"))s.getJSONArray("segments").put(new JSONArray().put(s.getLong("anchor")).put(Math.min(at,s.getLong("deadline"))));s.put("status","paused").put("remaining",Math.max(0,s.getLong("deadline")-at)).put("deadline",0).put("anchor",0);break;
    case "resume":if(s.optString("status").equals("running"))break;if(!Arrays.asList("ready","paused").contains(s.optString("status")))throw new IllegalArgumentException("Timer is not ready to resume.");s.put("status","running").put("deadline",at+s.getLong("remaining")).put("anchor",s.getString("phase").equals("work")?at:0);break;
    case "end":record(s,"ended",at);s.put("status","finished").put("remaining",0).put("deadline",0).put("anchor",0);break;
    case "reset":record(s,"reset",at);s.put("id",UUID.randomUUID().toString()).put("phase","work").put("status","ready").put("remaining",s.getLong("work_ms")).put("deadline",0).put("anchor",0).put("segments",new JSONArray());break;
    case "skip_break":if(!s.optString("phase").equals("break"))throw new IllegalArgumentException("No break to skip.");next(s);break;
    default:throw new IllegalArgumentException("Unsupported focus action.");
   }
  }
  save(s);db.setTransactionSuccessful();
 }finally{db.endTransaction();}return snapshot(at);}}
 private long overlap(JSONArray segments,long lo,long hi) throws Exception {long result=0;for(int i=0;i<segments.length();i++){JSONArray v=segments.getJSONArray(i);result+=Math.max(0,Math.min(v.getLong(1),hi)-Math.max(v.getLong(0),lo));}return result;}
 JSONObject snapshot(long at) throws Exception {synchronized(LOCK){advance(at);JSONObject s=active();ZoneId zone=ZoneId.systemDefault();LocalDate day=Instant.ofEpochMilli(at).atZone(zone).toLocalDate();long lo=day.atStartOfDay(zone).toInstant().toEpochMilli(),hi=day.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli(),total=0;int completed=0,ended=0;
  JSONArray history=store.rows("SELECT * FROM focus_history ORDER BY ended DESC LIMIT 10000");for(int i=0;i<history.length();i++){JSONObject r=history.getJSONObject(i);total+=overlap(new JSONArray(r.getString("segments")),lo,hi);if(r.getLong("ended")>=lo&&r.getLong("ended")<hi){ended++;if(r.getString("status").equals("completed"))completed++;}}
  if(s.has("id")&&s.getString("phase").equals("work")&&!s.getString("status").equals("finished")){total+=overlap(s.getJSONArray("segments"),lo,hi);if(s.getString("status").equals("running"))total+=Math.max(0,Math.min(Math.min(at,s.getLong("deadline")),hi)-Math.max(s.getLong("anchor"),lo));}
  if(s.optString("status").equals("running"))s.put("remaining",Math.max(0,s.getLong("deadline")-at));
  JSONObject defaults=new JSONObject().put("work_minutes",45).put("break_minutes",10).put("rounds",3).put("quiet",false).put("auto_break",true);
  JSONArray recent=new JSONArray();for(int i=0;i<Math.min(10,history.length());i++){JSONObject r=history.getJSONObject(i);recent.put(new JSONObject().put("title",r.getString("title")).put("status",r.getString("status")).put("ended",r.getLong("ended")).put("focused_ms",overlap(new JSONArray(r.getString("segments")),0,Long.MAX_VALUE)));}
  return new JSONObject().put("active",s).put("recent",recent).put("tasks",store.rows("SELECT * FROM focus_tasks ORDER BY done,created DESC LIMIT 200")).put("stats",new JSONObject().put("focused_ms",total).put("completed",completed).put("completion",ended==0?JSONObject.NULL:Math.round(completed*100.0/ended))).put("defaults",store.meta("focus_defaults",defaults)).put("choice",store.meta("focus_choice",new JSONObject()));
 }}
 private static Intent intent(Context c){return new Intent(c,FocusReceiver.class).setData(Uri.parse("bujji://deep-work/timer"));}
 static void recover(Context c,Store store) throws Exception {synchronized(LOCK){
  DeepWork work=new DeepWork(store);JSONObject legacy=store.meta("focus",new JSONObject());
  if(!work.active().has("id")&&legacy.has("id")){JSONObject old=store.reminder(legacy.optString("id"));if(old!=null&&old.optString("status").equals("pending")){
   long start=legacy.optLong("start"),end=legacy.optLong("end"),duration=end-start;if(duration>=60000&&duration<=10800000){JSONObject s=new JSONObject().put("id",old.getString("id")).put("title",old.getString("title")).put("task_id","").put("work_ms",duration).put("break_ms",0).put("rounds",1).put("round",1).put("phase","work").put("status","running").put("remaining",duration).put("deadline",end).put("anchor",start).put("segments",new JSONArray()).put("quiet",false).put("auto_break",true);work.save(s);}store.cancel(old.getString("id"));Reminders.cancel(c,old);}
   store.putMeta("focus",new JSONObject());
  }
  work.advance(System.currentTimeMillis());JSONArray signals=store.rows("SELECT * FROM focus_signals WHERE delivered=0 ORDER BY id LIMIT 20");for(int i=0;i<signals.length();i++){JSONObject signal=signals.getJSONObject(i);ContentValues v=new ContentValues();v.put("delivered",1);if(store.getWritableDatabase().update("focus_signals",v,"id=? AND delivered=0",new String[]{signal.getString("id")})>0)Reminders.notify(c,880000+signal.getInt("id"),Reminders.FOCUS,"Bujji Focus",signal.getString("body"));}
  PendingIntent alarm=PendingIntent.getBroadcast(c,870001,intent(c),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);AlarmManager manager=c.getSystemService(AlarmManager.class);JSONObject a=work.active();if(!a.optString("status").equals("running")){manager.cancel(alarm);alarm.cancel();return;}
  long at=Math.max(System.currentTimeMillis()+1000,a.getLong("deadline"));if(Reminders.precise(c)){try{manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarm);return;}catch(SecurityException revoked){}}manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarm);
 }}
}
