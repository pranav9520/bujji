package org.bujji.companion;
import android.content.*;
public final class ReminderReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context,Intent intent){String id=intent.getStringExtra("id");if(id==null||!id.matches("[a-fA-F0-9-]{36}"))return;PendingResult result=goAsync();java.util.concurrent.ExecutorService worker=java.util.concurrent.Executors.newSingleThreadExecutor();worker.execute(()->{try(Store store=new Store(context)){Reminders.fire(context,store,id);}finally{result.finish();worker.shutdown();}});}
}
