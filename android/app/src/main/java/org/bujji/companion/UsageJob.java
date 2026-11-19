package org.bujji.companion;
import android.app.job.*;
import android.content.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
public final class UsageJob extends JobService {
 private static final int ID=62001;private final ExecutorService executor=Executors.newSingleThreadExecutor();private Future<?> work;private final AtomicInteger generation=new AtomicInteger();
 static void schedule(Context c,boolean enabled){JobScheduler jobs=c.getSystemService(JobScheduler.class);if(!enabled){jobs.cancel(ID);return;}jobs.schedule(new JobInfo.Builder(ID,new ComponentName(c,UsageJob.class)).setPeriodic(15*60_000L,5*60_000L).setPersisted(true).build());}
 @Override public boolean onStartJob(JobParameters params){int run=generation.incrementAndGet();work=executor.submit(()->{try(Store store=new Store(this)){if(run==generation.get())UsageTracker.nudge(this,store);}catch(Exception ignored){/* Retry on the next OS-scheduled check; no private logs. */}finally{if(run==generation.get())jobFinished(params,false);}});return true;}
 @Override public boolean onStopJob(JobParameters params){generation.incrementAndGet();if(work!=null)work.cancel(true);return true;}
 @Override public void onDestroy(){generation.incrementAndGet();executor.shutdownNow();super.onDestroy();}
}
