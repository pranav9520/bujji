package org.bujji.companion;
import java.util.*;

/** Union of foreground intervals: simultaneous resumed windows never double-count. */
public final class UsageMath {
 public static final class Event {
  public static final int RESUME=1,PAUSE=2,OFF=3,ON=4;
  public final long at;public final int type;public final String activity,pkg;
  public Event(long at,int type,String activity,String pkg){this.at=at;this.type=type;this.activity=activity;this.pkg=pkg;}
 }
 public static final class Result {public long total;public final Map<String,Long> apps=new HashMap<>();}
 public static Result compute(List<Event> events,long start,long end){
  Result result=new Result();LinkedHashMap<String,String> active=new LinkedHashMap<>();boolean interactive=true;long cursor=start;
  List<Event> sorted=new ArrayList<>(events);sorted.sort(Comparator.comparingLong(e->e.at));
  for(Event e:sorted){if(e.at>end)break;long at=Math.max(start,e.at);
   if(at>cursor&&interactive&&!active.isEmpty()){String pkg=null;for(String value:active.values())pkg=value;long delta=at-cursor;result.total+=delta;result.apps.put(pkg,result.apps.getOrDefault(pkg,0L)+delta);}
   if(e.type==Event.OFF){interactive=false;active.clear();}
   else if(e.type==Event.ON)interactive=true;
   else if(e.type==Event.RESUME){active.remove(e.activity);active.put(e.activity,e.pkg);}
   else if(e.type==Event.PAUSE)active.remove(e.activity);
   cursor=Math.max(cursor,at);
  }
  if(end>cursor&&interactive&&!active.isEmpty()){String pkg=null;for(String value:active.values())pkg=value;long delta=end-cursor;result.total+=delta;result.apps.put(pkg,result.apps.getOrDefault(pkg,0L)+delta);}
  return result;
 }
 public static boolean quiet(int hour,int start,int end){return start==end?false:start<end?hour>=start&&hour<end:hour>=start||hour<end;}
 public static boolean shouldNudge(long usedMinutes,int budget,boolean quiet,int count,long last,long now,int intervalMinutes){return usedMinutes>=budget&&!quiet&&count<3&&(last==0||now-last>=intervalMinutes*60_000L);}
 private UsageMath(){}
}
