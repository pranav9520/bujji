package org.bujji.companion;
import android.content.*;
import java.util.Arrays;
public final class BootReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context,Intent intent){if(!Arrays.asList(Intent.ACTION_BOOT_COMPLETED,Intent.ACTION_MY_PACKAGE_REPLACED,Intent.ACTION_TIME_CHANGED,Intent.ACTION_TIMEZONE_CHANGED).contains(intent.getAction()))return;PendingResult pending=goAsync();java.util.concurrent.ExecutorService worker=java.util.concurrent.Executors.newSingleThreadExecutor();worker.execute(()->{try(Store store=new Store(context)){try{DeepWork.recover(context,store);}catch(Exception ignored){}Reminders.recover(context,store);UsageJob.schedule(context,store.settings().optBoolean("usageEnabled"));}finally{pending.finish();worker.shutdown();}});}
}
