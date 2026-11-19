package org.bujji.companion;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.MediaRecorder;
import android.net.*;
import android.os.*;
import android.provider.*;
import android.speech.tts.*;
import android.view.*;
import android.webkit.*;
import android.widget.FrameLayout;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class MainActivity extends Activity {
    private DeviceSync deviceSync;private WebView web;private Store store;private SecretVault vault;private Cloud cloud;private TextToSpeech tts;
    private final Handler main=new Handler(Looper.getMainLooper());private final ExecutorService io=Executors.newFixedThreadPool(2);
    private volatile boolean trusted=false,resumed=false,destroyed=false;private volatile int chatEpoch=0;private final AtomicBoolean cloudBusy=new AtomicBoolean();
    private final Map<String,Rules.Plan> plans=new ConcurrentHashMap<>();private final List<String[]> shortHistory=new ArrayList<>();
    private MediaRecorder recorder;private File audio;private String recordMode="normal",pendingRecord;private SilenceGate silence;private boolean heard;private int speechEpoch=0;private Runnable sample;
    private String exportRequest,importRequest,exportJson;private boolean ttsReady;private String pendingNav;
    private static final String ORIGIN="https://app.bujji.local/";
    @Override public void onCreate(Bundle state){
        super.onCreate(state);store=new Store(this);vault=new SecretVault(this);cloud=new Cloud(store,vault);deviceSync=new DeviceSync(this,store,vault);Reminders.channels(this);pendingNav=getIntent().getStringExtra("open");
        FrameLayout root=new FrameLayout(this);root.setBackgroundColor(Color.rgb(16,15,32));web=new WebView(this);root.addView(web,new FrameLayout.LayoutParams(-1,-1));setContentView(root);
        if(Build.VERSION.SDK_INT>=30){getWindow().setDecorFitsSystemWindows(false);root.setOnApplyWindowInsetsListener((view,insets)->{android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());android.graphics.Insets keyboard=insets.getInsets(WindowInsets.Type.ime());view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,keyboard.bottom));return insets;});}
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setBlockNetworkLoads(true);settings.setDomStorageEnabled(false);settings.setSaveFormData(false);settings.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptCookie(false);WebView.setWebContentsDebuggingEnabled(false);
        web.addJavascriptInterface(new Bridge(),"BujjiAndroid");
        web.setWebChromeClient(new WebChromeClient(){@Override public void onPermissionRequest(PermissionRequest request){request.deny();}});
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest request){return !request.getUrl().toString().equals(ORIGIN+"index.html");}
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();String name=uri.getPath()==null?"":uri.getPath().replaceFirst("^/","");
                if(!"https".equals(uri.getScheme())||!"app.bujji.local".equals(uri.getHost())||!Arrays.asList("index.html","app.css","app.js").contains(name))return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));
                try{Map<String,String> headers=new HashMap<>();headers.put("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'");headers.put("Cache-Control","no-store");headers.put("X-Content-Type-Options","nosniff");return new WebResourceResponse(name.endsWith("css")?"text/css":name.endsWith("js")?"application/javascript":"text/html","UTF-8",200,"OK",headers,getAssets().open(name));}catch(IOException e){return new WebResourceResponse("text/plain","UTF-8",404,"Missing",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
            }
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap icon){trusted=false;}
            @Override public void onPageFinished(WebView view,String url){trusted=(ORIGIN+"index.html").equals(url);if(trusted){event("ready",new JSONObject());navigatePending();}}
        });
        web.loadUrl(ORIGIN+"index.html");
        tts=new TextToSpeech(this,status->main.post(()->{ttsReady=status==TextToSpeech.SUCCESS&&tts!=null&&!destroyed;if(ttsReady){tts.setLanguage(new Locale("en","IN"));tts.setSpeechRate(1f);}}));
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener(){@Override public void onStart(String id){event("speaking",obj("active",true));}@Override public void onDone(String id){event("speaking",obj("active",false));}@Override public void onError(String id){event("speaking",obj("active",false));event("error",obj("message","The device voice could not play. Text is still available."));}});
        io.execute(()->{try{DeepWork.recover(this,store);Reminders.recover(this,store);UsageJob.schedule(this,store.settings().optBoolean("usageEnabled"));}catch(Exception ignored){}});
    }
    @Override protected void onResume(){super.onResume();resumed=true;if(web!=null)web.onResume();event("resume",new JSONObject());if(store!=null)io.execute(()->{try{DeepWork.recover(this,store);Reminders.recover(this,store);}catch(Exception ignored){}});if(pendingRecord!=null&&checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED){String mode=pendingRecord;pendingRecord=null;main.postDelayed(()->startRecording(mode),250);}}
    @Override protected void onPause(){deviceSync.cancelControl();resumed=false;chatEpoch++;stopRecording(true);cloud.cancel();plans.clear();synchronized(shortHistory){shortHistory.clear();}if(tts!=null)tts.stop();event("paused",new JSONObject());if(web!=null)web.onPause();super.onPause();}
    @Override protected void onDestroy(){destroyed=true;trusted=false;cloud.cancel();stopRecording(true);if(tts!=null){tts.stop();tts.shutdown();}io.shutdownNow();if(web!=null){web.removeJavascriptInterface("BujjiAndroid");web.destroy();}store.close();super.onDestroy();}
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);pendingNav=intent.getStringExtra("open");navigatePending();}
    private void navigatePending(){if(trusted&&pendingNav!=null){String value=pendingNav;pendingNav=null;if(Arrays.asList("reminders","usage","focus").contains(value))event("navigate",obj("tab",value));}}
    private static JSONObject obj(String key,Object value){try{return new JSONObject().put(key,value);}catch(JSONException e){throw new IllegalStateException(e);}}
    private void event(String topic,JSONObject value){main.post(()->{if(!destroyed&&trusted)web.evaluateJavascript("window.Bujji && window.Bujji.event("+JSONObject.quote(topic)+","+value.toString()+")",null);});}
    private void reply(String id,Object result,Exception error){main.post(()->{if(destroyed||!trusted)return;try{JSONObject envelope=new JSONObject().put("id",id);if(error!=null)envelope.put("error",friendly(error));else envelope.put("result",result==null?JSONObject.NULL:result);web.evaluateJavascript("window.Bujji && window.Bujji.response("+envelope.toString()+")",null);}catch(JSONException ignored){}});}
    private String friendly(Exception e){if(e instanceof IllegalArgumentException||e instanceof IOException)return e.getMessage()==null?"The request did not finish. Please try again.":e.getMessage();if(e instanceof JSONException)return "The provider or saved data returned an invalid response. No proposed action ran.";return "Bujji could not finish that request. Check settings and try again.";}
    private final class Bridge {
        @JavascriptInterface public void call(String raw){if(raw==null||raw.length()>40000)return;try{JSONObject call=new JSONObject(raw);String id=call.getString("id"),action=call.getString("action");if(!id.matches("[A-Za-z0-9_-]{1,80}"))return;JSONObject p=call.optJSONObject("payload");if(p==null)p=new JSONObject();JSONObject payload=p;main.post(()->{if(!trusted||!resumed){reply(id,null,new IllegalArgumentException("Open Bujji to use this action."));return;}dispatch(id,action,payload);});}catch(JSONException ignored){}}
    }
    private void dispatch(String id,String action,JSONObject p){
        switch(action){
            case "remoteStop":deviceSync.cancelControl();break;
            case "record":{String mode=p.optString("mode","normal");if(!Arrays.asList("normal","short","remote","remote-files").contains(mode)){reply(id,null,new IllegalArgumentException("Unknown recording mode"));return;}if(!vault.has(AIRouting.speech(store.settings()))){reply(id,null,new IllegalArgumentException("Set up your AI model and key before voice transcription. Typed reminders and Clock work without AI."));return;}if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){pendingRecord=mode;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},10);reply(id,obj("permissionRequested",true),null);}else{startRecording(mode);reply(id,obj("recording",true),null);}return;}
            case "stopRecording":stopRecording(false);reply(id,obj("stopped",true),null);return;
            case "stop":deviceSync.cancelControl();chatEpoch++;stopRecording(true);cloud.cancel();plans.clear();if(tts!=null)tts.stop();reply(id,obj("stopped",true),null);return;
            case "endShort":chatEpoch++;stopRecording(true);cloud.cancel();if(tts!=null)tts.stop();synchronized(shortHistory){shortHistory.clear();}reply(id,obj("cleared",true),null);return;
            case "speak":if(ttsReady){tts.speak(p.optString("text").substring(0,Math.min(600,p.optString("text").length())),TextToSpeech.QUEUE_FLUSH,null,"bujji");reply(id,obj("requested",true),null);}else reply(id,null,new IllegalArgumentException("No device voice is ready. Configure Android text-to-speech first."));return;
            case "permission":permission(id,p.optString("kind"));return;
            case "help":{String which=p.optString("which");String url=which.equals("gemini")?"https://aistudio.google.com/apikey":which.equals("groq")?"https://console.groq.com/keys":which.equals("openai")?"https://platform.openai.com/api-keys":which.equals("anthropic")?"https://platform.claude.com/settings/keys":which.equals("perplexity")?"https://www.perplexity.ai/account/api/keys":"https://github.com";try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));reply(id,obj("opened",true),null);}catch(ActivityNotFoundException e){reply(id,null,new IllegalArgumentException("No browser is available."));}return;}
            case "remoteDownload":{if(Build.VERSION.SDK_INT>=29){io.execute(()->{try{reply(id,deviceSync.saveDownload(p.getString("path")),null);}catch(Exception e){reply(id,null,e);}});return;}if(remoteDownloadRequest!=null){reply(id,null,new IllegalArgumentException("Finish the current save dialog first."));return;}remoteDownloadPath=p.optString("path");if(remoteDownloadPath.isEmpty()||remoteDownloadPath.length()>2000){reply(id,null,new IllegalArgumentException("Select a laptop file first."));return;}remoteDownloadRequest=id;String name=remoteDownloadPath.replace('\\','/');name=name.substring(name.lastIndexOf('/')+1);try{startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,name),22);}catch(Exception e){remoteDownloadRequest=null;reply(id,null,new IllegalArgumentException("No file picker is available."));}return;}
            case "export":exportRequest=id;io.execute(()->{try{exportJson=store.backup().toString();main.post(()->{Intent pick=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,"Bujji-backup-"+LocalDate.now()+".json");startActivityForResult(pick,20);});}catch(Exception e){reply(id,null,e);}});return;
            case "import":importRequest=id;startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json"),21);return;
        }
        io.execute(()->{try{Object result;
            switch(action){
                case "state":result=state();break;
                case "remoteStatus":result=deviceSync.remote("status",new JSONObject());break;
                case "remoteFiles":result=deviceSync.remote("files",p);break;
                case "remoteControl":result=deviceSync.remote("control",p);break;
                case "remoteStop":deviceSync.cancelControl();result=deviceSync.remote("control",new JSONObject().put("operation","stop"));break;
                case "workFocus":new DeepWork(store).action(p,System.currentTimeMillis());DeepWork.recover(this,store);result=state();break;
                case "pairLaptop":result=deviceSync.pair(p);break;
                case "syncLaptop":result=deviceSync.sync();break;
                case "disconnectLaptop":deviceSync.disconnect();result=state();break;
                case "settings":result=saveSettings(p);break;
                case "clearKey":{String provider=p.optString("provider",store.settings().optString("provider","gemini"));if(!AIRouting.PROVIDERS.contains(provider))throw new IllegalArgumentException("Unknown AI provider");cloud.cancel();vault.clear(provider);result=state();break;}
                case "chat":result=chat(p);break;
                case "approve":result=approve(p.getString("id"),p.optBoolean("confirmed"));break;
                case "memoryAdd":store.addMemory(p.getString("text"));result=state();break;
                case "memoryRemove":store.removeMemory(p.getString("id"));result=state();break;
                case "reminderAdd":{JSONObject r=store.addReminder(p.getString("title"),p.getLong("at"),p.optString("repeat","none"),"reminder");Reminders.schedule(this,r);result=state();break;}
                case "reminderCancel":{JSONObject r=store.reminder(p.getString("id"));store.cancel(p.getString("id"));Reminders.cancel(this,r);getSystemService(NotificationManager.class).cancel(r==null?0:r.optInt("slot"));result=state();break;}
                case "reminderComplete":{String key=p.getString("id");JSONObject r=store.claim(key,System.currentTimeMillis(),true);Reminders.cancel(this,r);Reminders.schedule(this,store.reminder(key));result=state();break;}
                case "focusStart":{Rules.Plan plan=new Rules.Plan("focus");plan.title=Rules.bounded(p.optString("title","Focus session"),100);int minutes=p.optInt("minutes",25);if(minutes<1||minutes>180)throw new IllegalArgumentException("Choose 1–180 minutes.");plan.duration=minutes*60_000L;result=perform(plan);break;}
                case "focusStop":stopFocus();result=state();break;
                case "clock":{Rules.Plan plan=new Rules.Plan("clock");plan.title=Rules.bounded(p.optString("title","Bujji alarm"),100);plan.at=p.getLong("at");Rules.future(plan.at);openClock(plan);result=obj("message","Clock handoff requested. Confirm the day and time in Clock; Bujji cannot verify that an alarm was set.");break;}
                case "usage":result=UsageTracker.today(this);break;
                case "usageCheck":UsageTracker.nudge(this,store);result=UsageTracker.today(this);break;
                case "testNotification":result=obj("requested",Reminders.notify(this,900001,Reminders.CHANNEL,"Bujji notification test","If you can see this, notification permission is working. Sound depends on Android channel and volume settings."));break;
                default:throw new IllegalArgumentException("Unsupported phone action.");
            }
            reply(id,result,null);
        }catch(Exception e){reply(id,null,e);}});
    }
    private String remoteDownloadRequest,remoteDownloadPath;
    private JSONObject state() throws Exception {DeepWork.recover(this,store);JSONObject result=store.snapshot();JSONObject s=result.getJSONObject("settings");s.put("hasKey",vault.has(s.optString("provider","gemini")));result.put("permissions",new JSONObject().put("notifications",Reminders.canNotify(this)).put("precise",Reminders.precise(this)).put("usage",UsageTracker.permitted(this)).put("microphone",checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED));result.put("deepFocus",new DeepWork(store).snapshot(System.currentTimeMillis()));result.put("ai",AIRouting.status(s,vault));result.put("version","1.0.0");result.put("pairing",deviceSync.status());result.put("laptopPaired",vault.has("laptop"));return result;}
    private JSONObject saveSettings(JSONObject p) throws Exception {
        List<String> allowed=Arrays.asList("name","provider","model","apiKey","speak","focusMode","usageEnabled","budgetMinutes","nudgeInterval","quietStart","quietEnd","models","routes","speechProvider","taskMode");Iterator<String> keys=p.keys();while(keys.hasNext())if(!allowed.contains(keys.next()))throw new IllegalArgumentException("Unsupported setting");
        JSONObject s=store.settings();if(p.has("name"))s.put("name",Rules.bounded(p.getString("name"),40));if(p.has("provider")){if(!AIRouting.PROVIDERS.contains(p.getString("provider")))throw new IllegalArgumentException("Unknown AI provider");if(!s.has("speechProvider"))s.put("speechProvider",AIRouting.speech(s));if(!s.has("dailyProvider"))s.put("dailyProvider",s.optString("provider","gemini"));s.put("models",AIRouting.models(s));s.put("provider",p.getString("provider"));}
        if(p.has("model")){String model=p.getString("model").trim();if(model.length()>150||model.contains("\n")||model.contains("\r"))throw new IllegalArgumentException("Use a valid model ID");s.put("model",model);JSONObject models=AIRouting.models(s);models.put(s.getString("provider"),model);s.put("models",models);}
        if(p.has("models")){JSONObject m=p.getJSONObject("models"),out=AIRouting.models(s);Iterator<String> names=m.keys();while(names.hasNext()){String key=names.next(),value=m.getString(key).trim();if(!AIRouting.PROVIDERS.contains(key)||value.length()>150||!value.matches("[A-Za-z0-9._:/-]*"))throw new IllegalArgumentException("Invalid provider model ID");out.put(key,value);}s.put("models",out);}
        if(p.has("routes")){JSONObject routes=p.getJSONObject("routes");if(routes.length()!=AIRouting.TASKS.size())throw new IllegalArgumentException("Choose every task route");for(String task:AIRouting.TASKS)if(!AIRouting.PROVIDERS.contains(routes.getString(task))||(task.equals("daily")&&routes.getString(task).equals("perplexity")))throw new IllegalArgumentException("Invalid task provider");s.put("routes",routes);}
        if(p.has("speechProvider")){String value=p.getString("speechProvider");if(!Arrays.asList("gemini","groq").contains(value))throw new IllegalArgumentException("Voice input uses Gemini or Groq");s.put("speechProvider",value);}
        if(p.has("taskMode")){String value=p.getString("taskMode");if(!value.equals("auto")&&!AIRouting.TASKS.contains(value))throw new IllegalArgumentException("Unknown task category");s.put("taskMode",value);}
        for(String key:Arrays.asList("speak","focusMode","usageEnabled"))if(p.has(key))s.put(key,p.getBoolean(key));
        for(String key:Arrays.asList("budgetMinutes","nudgeInterval","quietStart","quietEnd"))if(p.has(key)){int value=p.getInt(key);int min=key.equals("budgetMinutes")?15:key.equals("nudgeInterval")?15:0;int max=key.equals("budgetMinutes")?1440:key.equals("nudgeInterval")?240:23;if(value<min||value>max)throw new IllegalArgumentException("That screen-time setting is out of range.");s.put(key,value);}
        if(p.has("apiKey")&&!p.getString("apiKey").trim().isEmpty())vault.save(s.getString("provider"),p.getString("apiKey"));store.putMeta("settings",s);UsageJob.schedule(this,s.optBoolean("usageEnabled"));return state();
    }
    private JSONObject chat(JSONObject p) throws Exception {
        if(!cloudBusy.compareAndSet(false,true))throw new IllegalArgumentException("Wait for the current reply or tap Stop.");
        try{int run=chatEpoch;String message=Rules.bounded(p.optString("text"),4000);boolean temporary=p.optString("mode").equals("short");
            if(!temporary){store.message("user",message,"phone");Rules.Plan local=Rules.parse(message,ZonedDateTime.now());if(local!=null){if(local.type.equals("usage"))return obj("reply","Open Screen time to see this phone's estimate.").put("navigate","usage");return prepared(local);}}
            if(!temporary&&vault.has("laptop")&&(p.optBoolean("laptopFiles")||((java.util.Arrays.asList("auto","daily").contains(store.settings().optString("taskMode","auto"))||message.toLowerCase(java.util.Locale.ROOT).matches("(?s).*\\b(laptop|downloads|desktop)\\b.*"))&&laptopFilesIntent(message)))){
                JSONObject result=deviceSync.remote("chat",new JSONObject().put("message",message));if(run!=chatEpoch||!resumed)throw new IllegalArgumentException("File search stopped.");
                JSONArray files=result.optJSONArray("files");if(files==null)files=new JSONArray();String text=result.optString("reply","Found these files.");
                if(result.optBoolean("auto_save")&&files.length()==1&&Build.VERSION.SDK_INT>=29){try{JSONObject saved=deviceSync.saveDownload(files.getJSONObject(0).getString("path"));files.getJSONObject(0).put("saved",true);text+="\n\n"+saved.getString("message");}catch(Exception e){text+="\n\nTransfer did not finish: "+friendly(e)+" Tap Save to retry.";}}
                store.fileMessage(text,files);return obj("reply",text).put("files",files);
            }
            List<String[]> context; synchronized(shortHistory){context=new ArrayList<>(shortHistory);}
            Cloud.Answer answer=cloud.reply(message,temporary,context);
            if(run!=chatEpoch||!resumed)throw new IllegalArgumentException("Reply stopped. No proposed action ran.");
            if(!temporary){store.message("assistant",answer.text,answer.provider);if(answer.plan!=null){plans.put(answer.plan.id,answer.plan);return obj("reply",answer.text).put("plan",planJson(answer.plan));}}
            else synchronized(shortHistory){shortHistory.add(new String[]{"user",message});shortHistory.add(new String[]{"assistant",answer.text});while(shortHistory.size()>8)shortHistory.remove(0);}
            return obj("reply",answer.text);
        }finally{cloudBusy.set(false);}
    }
    static boolean laptopFilesIntent(String message){String t=message.toLowerCase(java.util.Locale.ROOT);boolean location=t.matches("(?s).*\\b(laptop|downloads|desktop|file explorer|my files)\\b.*"),noun=t.matches("(?s).*\\b(file|files|folder|folders|pdf|docx?|document|documents|assignment|notes|certificate|certificates|image|images|photo|photos|spreadsheet|invoice|png|jpe?g|xlsx|pptx|txt|zip)\\b.*");if(!location&&t.matches("(?s).*\\b(explain|meaning|code|program|teach)\\b.*"))return false;if(location&&!noun)return t.matches("(?s).*\\b(open|show|list|browse)\\b.*");return noun&&(location||t.matches("(?s).*\\b(find|search|send|download|transfer|read|open|show|list|fetch|get|pampu|pampinchu|vethuku|vethiki|choopinchu)\\b.*"));}
    private JSONObject prepared(Rules.Plan p) throws Exception {plans.put(p.id,p);String text="Review this "+(p.type.equals("clock")?"Clock request":p.type.equals("memory")?"memory":p.type.equals("focus")?"focus session":"reminder")+" below. Nothing has run yet.";store.message("assistant",text,"local");return obj("reply",text).put("plan",planJson(p));}
    private JSONObject planJson(Rules.Plan p) throws Exception {return new JSONObject().put("id",p.id).put("type",p.type).put("title",p.title).put("text",p.text).put("at",p.at).put("duration",p.duration);}
    private JSONObject approve(String id,boolean confirmed) throws Exception {Rules.Plan plan=plans.remove(id);if(plan==null||plan.expires<System.currentTimeMillis())throw new IllegalArgumentException("That review expired. Ask again.");if(!confirmed)return obj("message","Cancelled. Nothing ran.");JSONObject result=perform(plan);store.message("assistant",result.optString("message","Saved on this phone."),"local");return result;}
    private JSONObject perform(Rules.Plan p) throws Exception {
        switch(p.type){
            case "memory":store.addMemory(p.text);return obj("message","Memory saved on this phone.");
            case "reminder":{Rules.future(p.at);JSONObject row=store.addReminder(p.title,p.at,p.repeat,"reminder");Reminders.schedule(this,row);return obj("message","Reminder saved for "+Rules.label(p.at)+"."+(!Reminders.canNotify(this)?" Enable notifications for alerts.":!Reminders.precise(this)?" Precise-reminder access is off, so Android may delay it.":""));}
            case "clock":Rules.future(p.at);openClock(p);return obj("message","Clock handoff requested. Confirm the day and time in Clock; Bujji cannot verify an alarm was set.");
            case "focus":{new DeepWork(store).action(new JSONObject().put("action","start").put("title",p.title).put("work_minutes",p.duration/60000).put("break_minutes",10).put("rounds",1).put("auto_break",true),System.currentTimeMillis());DeepWork.recover(this,store);return obj("message","Focus session started.");}
            default:throw new IllegalArgumentException("Unsupported phone action");
        }
    }
    private void stopFocus() throws Exception {JSONObject s=new DeepWork(store).active();if(s.has("id")&&!s.optString("status").equals("finished"))new DeepWork(store).action(obj("action","end"),System.currentTimeMillis());DeepWork.recover(this,store);}
    private void openClock(Rules.Plan p){main.post(()->{if(!resumed)return;ZonedDateTime at=Instant.ofEpochMilli(p.at).atZone(ZoneId.systemDefault());Runnable launch=()->{try{startActivity(new Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR,at.getHour()).putExtra(AlarmClock.EXTRA_MINUTES,at.getMinute()).putExtra(AlarmClock.EXTRA_MESSAGE,p.title+" · "+Rules.label(p.at)).putExtra(AlarmClock.EXTRA_SKIP_UI,false));}catch(ActivityNotFoundException e){event("error",obj("message","No Clock app accepted this request. Set the alarm manually in your Clock app."));}};
        if(!Rules.clockCanExpress(p.at,ZonedDateTime.now()))new AlertDialog.Builder(this).setTitle("Check the day in Clock").setMessage("Android can pass the time, but this Clock handoff cannot specify that date. Choose the correct day in Clock, or use a Bujji reminder instead.").setPositiveButton("Open Clock",(d,w)->launch.run()).setNegativeButton("Cancel",null).show();else launch.run();});}
    private void permission(String id,String kind){try{switch(kind){
        case "notifications":if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},11);else startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName()));break;
        case "precise":if(Build.VERSION.SDK_INT>=31)startActivity(new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+getPackageName())));break;
        case "usage":startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS,Uri.parse("package:"+getPackageName())));break;
        case "battery":startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName())));break;
        default:throw new IllegalArgumentException("Unknown permission");}
        reply(id,obj("opened",true),null);
    }catch(Exception e){reply(id,null,new IllegalArgumentException("Open Android Settings → Apps → Bujji to change this permission."));}}
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants){super.onRequestPermissionsResult(code,permissions,grants);if(code==10&&pendingRecord!=null){String mode=pendingRecord;pendingRecord=null;if(grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED){if(resumed)main.postDelayed(()->startRecording(mode),250);else pendingRecord=mode;}else event("error",obj("message","Microphone permission was not granted. You can still type."));}event("refresh",new JSONObject());}
    private void startRecording(String mode){if(!resumed||destroyed||recorder!=null)return;if(cloudBusy.get()){event("error",obj("message","Wait for the reply or tap Stop first."));return;}
        try{recordMode=mode;audio=new File(getCacheDir(),"speech-"+UUID.randomUUID()+".m4a");recorder=new MediaRecorder();recorder.setAudioSource(MediaRecorder.AudioSource.MIC);recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);recorder.setAudioChannels(1);recorder.setAudioSamplingRate(16000);recorder.setAudioEncodingBitRate(48000);recorder.setOutputFile(audio.getAbsolutePath());recorder.prepare();recorder.start();heard=false;silence=new SilenceGate(SystemClock.elapsedRealtime());int run=++speechEpoch;event("recording",obj("active",true));sample=()->{if(recorder==null||run!=speechEpoch)return;try{int level=recorder.getMaxAmplitude();long now=SystemClock.elapsedRealtime();boolean quiet=silence.update(level,now);heard=silence.heard;event("meter",obj("level",Math.min(1,level/10000.0)));if(quiet){stopRecording(false);return;}main.postDelayed(sample,120);}catch(RuntimeException e){stopRecording(true);event("error",obj("message","Microphone capture stopped. Please try again."));}};main.postDelayed(sample,120);
        }catch(Exception e){stopRecording(true);event("error",obj("message","The microphone could not start. Check permission and whether another app is using it."));}}
    private void stopRecording(boolean cancelled){if(cancelled)speechEpoch++;if(sample!=null)main.removeCallbacks(sample);if(recorder==null)return;boolean valid=true;try{recorder.stop();}catch(RuntimeException e){valid=false;}recorder.release();recorder=null;File file=audio;audio=null;event("recording",obj("active",false));if(cancelled||!valid||!heard||file==null||file.length()<1000){if(file!=null)file.delete();speechEpoch++;if(!cancelled)event("error",obj("message","No clear speech was detected. Tap to try again."));return;}int run=speechEpoch;String mode=recordMode;if(!cloudBusy.compareAndSet(false,true)){file.delete();return;}event("phase",obj("message","Understanding your voice…"));io.execute(()->{try{String text=cloud.transcribe(file);cloudBusy.set(false);if(!text.isEmpty()&&run==speechEpoch&&resumed)event("transcript",new JSONObject().put("text",text).put("mode",mode).put("confirm",store.settings().optBoolean("focusMode")));else if(text.isEmpty())event("error",obj("message","No clear words were returned. You can still type."));}catch(Exception e){if(run==speechEpoch&&resumed)event("error",obj("message",friendly(e)));}finally{file.delete();cloudBusy.set(false);}});}
    @Override protected void onActivityResult(int code,int result,Intent data){super.onActivityResult(code,result,data);if(code==22){String rid=remoteDownloadRequest,rpath=remoteDownloadPath;remoteDownloadRequest=null;remoteDownloadPath=null;if(rid==null)return;if(result!=RESULT_OK||data==null||data.getData()==null){reply(rid,obj("cancelled",true),null);return;}Uri target=data.getData();io.execute(()->{try{deviceSync.download(rpath,target);reply(rid,obj("message","File saved on this phone."),null);}catch(Exception e){reply(rid,null,e);}});return;}if(code!=20&&code!=21)return;String id=code==20?exportRequest:importRequest;if(id==null)return;if(result!=RESULT_OK||data==null||data.getData()==null){reply(id,obj("cancelled",true),null);return;}Uri uri=data.getData();io.execute(()->{try{if(code==20){try(OutputStream out=getContentResolver().openOutputStream(uri)){if(out==null)throw new IOException("The backup file could not be opened.");out.write(exportJson.getBytes(StandardCharsets.UTF_8));}exportJson=null;reply(id,obj("message","Backup saved. It contains local conversations and memories, but no API keys."),null);}else{byte[] raw=Cloud.read(getContentResolver().openInputStream(uri),5_000_000);JSONObject backup=new JSONObject(new String(raw,StandardCharsets.UTF_8));store.restore(backup);DeepWork.recover(this,store);Reminders.recover(this,store);reply(id,obj("message","Backup merged. Existing record IDs were kept. API keys were not imported."),null);}}catch(Exception e){reply(id,null,e);}});}
}
