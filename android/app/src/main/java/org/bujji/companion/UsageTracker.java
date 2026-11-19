package org.bujji.companion;
import android.app.AppOpsManager;
import android.app.usage.*;
import android.content.*;
import android.os.Build;
import org.json.*;
import java.time.*;
import java.util.*;

final class UsageTracker {
 static boolean permitted(Context c){AppOpsManager a=c.getSystemService(AppOpsManager.class);int mode=Build.VERSION.SDK_INT>=29?a.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,android.os.Process.myUid(),c.getPackageName()):a.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,android.os.Process.myUid(),c.getPackageName());return mode==AppOpsManager.MODE_ALLOWED;}
 static JSONObject today(Context context) throws Exception {
  if(!permitted(context))return new JSONObject().put("permission",false);
  long now=System.currentTimeMillis(),start=LocalDate.now().atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli();UsageEvents stream=context.getSystemService(UsageStatsManager.class).queryEvents(start-86400_000L,now);
  List<UsageMath.Event> events=new ArrayList<>();UsageEvents.Event event=new UsageEvents.Event();int count=0;
  while(stream.hasNextEvent()){
   if(Thread.currentThread().isInterrupted())throw new InterruptedException();
   if(++count>80000)throw new IllegalArgumentException("Today's usage history is too large to estimate safely. Check Digital Wellbeing.");
   stream.getNextEvent(event);int type=event.getEventType(),mapped=0;
   if(type==UsageEvents.Event.ACTIVITY_RESUMED)mapped=UsageMath.Event.RESUME;else if(type==UsageEvents.Event.ACTIVITY_PAUSED)mapped=UsageMath.Event.PAUSE;
   else if(type==UsageEvents.Event.SCREEN_NON_INTERACTIVE||type==UsageEvents.Event.KEYGUARD_SHOWN)mapped=UsageMath.Event.OFF;
   else if(type==UsageEvents.Event.SCREEN_INTERACTIVE||type==UsageEvents.Event.KEYGUARD_HIDDEN)mapped=UsageMath.Event.ON;
   if(mapped!=0){String pkg=event.getPackageName()==null?"":event.getPackageName();String key=pkg+"/"+event.getClassName();events.add(new UsageMath.Event(event.getTimeStamp(),mapped,key,pkg));}
  }
  UsageMath.Result result=UsageMath.compute(events,start,now);JSONArray apps=new JSONArray();List<Map.Entry<String,Long>> entries=new ArrayList<>(result.apps.entrySet());entries.sort((a,b)->Long.compare(b.getValue(),a.getValue()));
  for(int i=0;i<Math.min(8,entries.size());i++){Map.Entry<String,Long> entry=entries.get(i);String label=entry.getKey();try{label=context.getPackageManager().getApplicationLabel(context.getPackageManager().getApplicationInfo(entry.getKey(),0)).toString();}catch(android.content.pm.PackageManager.NameNotFoundException ignored){}apps.put(new JSONObject().put("name",label).put("minutes",entry.getValue()/60000));}
  return new JSONObject().put("permission",true).put("minutes",result.total/60000).put("apps",apps).put("date",LocalDate.now().toString()).put("estimated",true);
 }
 static void nudge(Context c,Store store) throws Exception {
  JSONObject settings=store.settings();if(!settings.optBoolean("usageEnabled")||!permitted(c)||DeepWork.quiet(store))return;
  JSONObject usage=today(c),last=store.meta("usageLedger",new JSONObject());String date=LocalDate.now().toString();int count=date.equals(last.optString("date"))?last.optInt("count"):0;long instant=System.currentTimeMillis();long previous=date.equals(last.optString("date"))?last.optLong("last"):0;
  if(!UsageMath.shouldNudge(usage.optLong("minutes"),settings.optInt("budgetMinutes",480),UsageMath.quiet(LocalTime.now().getHour(),settings.optInt("quietStart",22),settings.optInt("quietEnd",7)),count,previous,instant,settings.optInt("nudgeInterval",60)))return;
  String[] messages={"You've crossed your phone-time budget. Ready for a little study time?","Your eyes deserve a rest. Step away from the screen for a few minutes.","That's a lot of phone time today. A short offline break could feel good."};
  if(!Thread.currentThread().isInterrupted()&&Reminders.notify(c,910000+count,Reminders.USAGE,"A gentle nudge",messages[count%messages.length]))store.putMeta("usageLedger",new JSONObject().put("date",date).put("count",count+1).put("last",instant));
 }
}
