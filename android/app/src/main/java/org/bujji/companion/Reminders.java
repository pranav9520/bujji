package org.bujji.companion;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import org.json.*;

final class Reminders {
    static final String CHANNEL="bujji-reminders",USAGE="bujji-usage",FOCUS="bujji-focus";
    static boolean canNotify(Context c){return ((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).areNotificationsEnabled();}
    static boolean precise(Context c){return Build.VERSION.SDK_INT<31||((AlarmManager)c.getSystemService(Context.ALARM_SERVICE)).canScheduleExactAlarms();}
    static void channels(Context c){NotificationManager n=c.getSystemService(NotificationManager.class);NotificationChannel reminders=new NotificationChannel(CHANNEL,"Reminders & focus",NotificationManager.IMPORTANCE_HIGH);reminders.setDescription("Reminders saved on this phone and focus session alerts.");n.createNotificationChannel(reminders);NotificationChannel usage=new NotificationChannel(USAGE,"Screen-time nudges",NotificationManager.IMPORTANCE_DEFAULT);usage.setDescription("Optional, limited wellbeing notifications.");n.createNotificationChannel(usage);n.createNotificationChannel(new NotificationChannel(FOCUS,"Focus sessions",NotificationManager.IMPORTANCE_HIGH));}
    private static Intent alarm(Context c,JSONObject r){return new Intent(c,ReminderReceiver.class).setData(Uri.parse("bujji://reminder/"+r.optString("id"))).putExtra("id",r.optString("id"));}
    static void cancel(Context c,JSONObject r){if(r==null)return;PendingIntent p=PendingIntent.getBroadcast(c,r.optInt("slot"),alarm(c,r),PendingIntent.FLAG_NO_CREATE|PendingIntent.FLAG_IMMUTABLE);if(p!=null){c.getSystemService(AlarmManager.class).cancel(p);p.cancel();}}
    static void schedule(Context c,JSONObject r){if(r==null||!r.optString("status").equals("pending"))return;PendingIntent p=PendingIntent.getBroadcast(c,r.optInt("slot"),alarm(c,r),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);AlarmManager manager=c.getSystemService(AlarmManager.class);long at=Math.max(System.currentTimeMillis()+1000,r.optLong("due"));if(precise(c)){try{manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,p);return;}catch(SecurityException revoked){/* Access can be revoked between check and scheduling. */}}manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,p);}
    static boolean notify(Context c,int id,String channel,String title,String text){channels(c);NotificationManager manager=c.getSystemService(NotificationManager.class);if(!canNotify(c)||manager.getNotificationChannel(channel).getImportance()==NotificationManager.IMPORTANCE_NONE)return false;
        PendingIntent tap=PendingIntent.getActivity(c,id,new Intent(c,MainActivity.class).putExtra("open",channel.equals(USAGE)?"usage":channel.equals(FOCUS)?"focus":"reminders").addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(c,channel).setSmallIcon(org.bujji.companion.R.drawable.ic_notification).setContentTitle(title).setContentText(text).setStyle(new Notification.BigTextStyle().bigText(text)).setAutoCancel(true).setContentIntent(tap).setOnlyAlertOnce(true).setCategory(Notification.CATEGORY_REMINDER).build();
        try{manager.notify(id,notification);return true;}catch(SecurityException e){return false;}
    }
    static void fire(Context c,Store store,String id){JSONObject r=store.claim(id,System.currentTimeMillis(),false);if(r==null){schedule(c,store.reminder(id));return;}
        boolean late=System.currentTimeMillis()-r.optLong("due")>60_000;boolean muted=!r.optString("kind").equals("focus")&&DeepWork.quiet(store);boolean shown=!muted&&notify(c,r.optInt("slot"),CHANNEL,r.optString("kind").equals("focus")?"Focus session finished":late?"Missed reminder":"Bujji reminder",r.optString("title"));store.outcome(id,r.optLong("due"),shown?(late?"missed_notified":"notified"):muted?"quiet_history":"notifications_off");
        schedule(c,store.reminder(id));JSONObject focus=store.meta("focus",new JSONObject());if(id.equals(focus.optString("id")))store.putMeta("focus",new JSONObject());
    }
    static void recover(Context c,Store store){JSONArray rows=store.pending();int missed=0;for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);if(r.optLong("due")<=System.currentTimeMillis()){if(missed++<3)fire(c,store,r.optString("id"));else{JSONObject claimed=store.claim(r.optString("id"),System.currentTimeMillis(),false);if(claimed!=null)store.outcome(claimed.optString("id"),claimed.optLong("due"),"missed_in_history");schedule(c,store.reminder(r.optString("id")));}}else schedule(c,r);}}
    private Reminders(){}
}
