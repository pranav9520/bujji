package org.bujji.companion;
import android.content.*;
public final class FocusReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context,Intent intent){PendingResult result=goAsync();java.util.concurrent.ExecutorService worker=java.util.concurrent.Executors.newSingleThreadExecutor();worker.execute(()->{try(Store store=new Store(context)){DeepWork.recover(context,store);}catch(Exception ignored){}finally{result.finish();worker.shutdown();}});}
}
