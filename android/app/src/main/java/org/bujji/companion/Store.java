package org.bujji.companion;

import android.content.*;
import android.database.Cursor;
import android.database.sqlite.*;
import org.json.*;
import java.util.*;

/** Device-private data with stable UUIDs, timestamps and tombstones for later sync. */
public final class Store extends SQLiteOpenHelper {
    public Store(Context context){super(context,"bujji-mobile.sqlite3",null,3);setWriteAheadLoggingEnabled(true);}
    @Override public void onCreate(SQLiteDatabase db){
        db.execSQL("CREATE TABLE messages(id TEXT PRIMARY KEY,role TEXT,body TEXT,created INTEGER,source TEXT)");
        db.execSQL("CREATE TABLE memories(id TEXT PRIMARY KEY,body TEXT,created INTEGER,updated INTEGER,deleted INTEGER DEFAULT 0)");
        db.execSQL("CREATE TABLE reminders(slot INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,title TEXT,due INTEGER,repeat_mode TEXT,kind TEXT,status TEXT,created INTEGER,updated INTEGER)");
        db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,reminder_id TEXT,due INTEGER,title TEXT,outcome TEXT,created INTEGER,UNIQUE(reminder_id,due))");
        db.execSQL("CREATE TABLE meta(name TEXT PRIMARY KEY,value TEXT)");
        syncTables(db);focusTables(db);
    }
    @Override public void onUpgrade(SQLiteDatabase db,int from,int to){if(from>=1&&to==3){if(from<2)syncTables(db);if(from<3)focusTables(db);return;}throw new IllegalStateException("A migration is required; existing data will not be dropped.");}
    private void focusTables(SQLiteDatabase db){db.execSQL("CREATE TABLE IF NOT EXISTS focus_history(id TEXT PRIMARY KEY,title TEXT,status TEXT,planned INTEGER,ended INTEGER,segments TEXT,task TEXT)");db.execSQL("CREATE TABLE IF NOT EXISTS focus_tasks(id TEXT PRIMARY KEY,title TEXT,done INTEGER,created INTEGER)");db.execSQL("CREATE TABLE IF NOT EXISTS focus_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,body TEXT,created INTEGER,delivered INTEGER DEFAULT 0)");}

    public JSONObject meta(String name,JSONObject fallback){try(Cursor c=getReadableDatabase().rawQuery("SELECT value FROM meta WHERE name=?",new String[]{name})){return c.moveToFirst()?new JSONObject(c.getString(0)):fallback;}catch(JSONException e){return fallback;}}
    public void putMeta(String name,JSONObject value){ContentValues cv=new ContentValues();cv.put("name",name);cv.put("value",value.toString());getWritableDatabase().insertWithOnConflict("meta",null,cv,SQLiteDatabase.CONFLICT_REPLACE);}
    public JSONObject settings(){JSONObject s=meta("settings",new JSONObject());try{
        if(!s.has("name"))s.put("name","");if(!s.has("provider"))s.put("provider","gemini");if(!s.has("model"))s.put("model","");if(!s.has("speak"))s.put("speak",false);if(!s.has("focusMode"))s.put("focusMode",false);
        if(!s.has("usageEnabled"))s.put("usageEnabled",false);if(!s.has("budgetMinutes"))s.put("budgetMinutes",480);if(!s.has("nudgeInterval"))s.put("nudgeInterval",60);if(!s.has("quietStart"))s.put("quietStart",22);if(!s.has("quietEnd"))s.put("quietEnd",7);
    }catch(JSONException impossible){throw new IllegalStateException(impossible);}return s;}
    public JSONArray rows(String sql,String...args){JSONArray array=new JSONArray();try(Cursor c=getReadableDatabase().rawQuery(sql,args)){while(c.moveToNext()){JSONObject row=new JSONObject();for(int i=0;i<c.getColumnCount();i++){try{row.put(c.getColumnName(i),c.isNull(i)?JSONObject.NULL:c.getType(i)==Cursor.FIELD_TYPE_INTEGER?c.getLong(i):c.getString(i));}catch(JSONException e){throw new IllegalStateException(e);}}array.put(row);}}return array;}
    public JSONArray messages(){return rows("SELECT * FROM (SELECT rowid AS n,* FROM messages ORDER BY created DESC,rowid DESC LIMIT 150) ORDER BY created,n");}
    public JSONArray context(){return rows("SELECT role,body FROM (SELECT rowid AS n,role,body,created FROM messages ORDER BY created DESC,rowid DESC LIMIT 12) ORDER BY created,n");}
    public JSONArray memories(){return rows("SELECT * FROM memories WHERE deleted=0 ORDER BY updated DESC LIMIT 200");}
    public JSONArray reminders(){return rows("SELECT * FROM reminders WHERE status!='cancelled' ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END,due LIMIT 200");}
    public JSONArray pending(){return rows("SELECT * FROM reminders WHERE status='pending' ORDER BY due LIMIT 2501");}
    public JSONObject reminder(String id){JSONArray a=rows("SELECT * FROM reminders WHERE id=?",id);return a.optJSONObject(0);}
    public String message(String role,String text,String source){if(!role.equals("user")&&!role.equals("assistant"))throw new IllegalArgumentException("Invalid message role");ContentValues v=new ContentValues();v.put("id",UUID.randomUUID().toString());v.put("role",role);v.put("body",Rules.bounded(text,8000));v.put("created",System.currentTimeMillis());v.put("source",source);getWritableDatabase().insertOrThrow("messages",null,v);return v.getAsString("id");}
    public void addMemory(String text){text=Rules.bounded(text,2000);if(rows("SELECT id FROM memories WHERE deleted=0 AND lower(body)=lower(?)",text).length()>0)return;long now=System.currentTimeMillis();ContentValues v=new ContentValues();v.put("id",UUID.randomUUID().toString());v.put("body",text);v.put("created",now);v.put("updated",now);getWritableDatabase().insertOrThrow("memories",null,v);}
    public void removeMemory(String id){ContentValues v=new ContentValues();v.put("deleted",1);v.put("updated",System.currentTimeMillis());getWritableDatabase().update("memories",v,"id=?",new String[]{id});}
    public JSONObject addReminder(String title,long due,String repeat,String kind){Rules.future(due);if(!Arrays.asList("none","daily","weekly").contains(repeat))throw new IllegalArgumentException("Unknown repeat setting");ContentValues v=new ContentValues();String id=UUID.randomUUID().toString();v.put("id",id);v.put("title",Rules.bounded(title,200));v.put("due",due);v.put("repeat_mode",repeat);v.put("kind",kind);v.put("status","pending");v.put("created",System.currentTimeMillis());v.put("updated",System.currentTimeMillis());getWritableDatabase().insertOrThrow("reminders",null,v);return reminder(id);}
    public void cancel(String id){ContentValues v=new ContentValues();v.put("status","cancelled");v.put("updated",System.currentTimeMillis());getWritableDatabase().update("reminders",v,"id=?",new String[]{id});}
    /** Atomic due claim: duplicate broadcasts cannot deliver one occurrence twice. */
    public JSONObject claim(String id,long now,boolean manual){SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{JSONObject r=reminder(id);if(r==null||!r.optString("status").equals("pending")||(!manual&&r.optLong("due")>now+1000))return null;
        ContentValues event=new ContentValues();event.put("reminder_id",id);event.put("due",r.optLong("due"));event.put("title",r.optString("title"));event.put("outcome",manual?"completed":"due");event.put("created",now);long inserted=db.insertWithOnConflict("events",null,event,SQLiteDatabase.CONFLICT_IGNORE);
        long next=Rules.nextDue(r.optLong("due"),r.optString("repeat_mode"),now,java.time.ZoneId.systemDefault());ContentValues v=new ContentValues();v.put("status",next<0?"done":"pending");if(next>=0)v.put("due",next);v.put("updated",now);db.update("reminders",v,"id=?",new String[]{id});db.setTransactionSuccessful();return inserted==-1?null:r;
    }finally{db.endTransaction();}}
    public void outcome(String id,long due,String outcome){ContentValues v=new ContentValues();v.put("outcome",outcome);getWritableDatabase().update("events",v,"reminder_id=? AND due=?",new String[]{id,Long.toString(due)});}
    public synchronized void markFileSaved(String path) throws JSONException {JSONObject files=meta("message_files",new JSONObject());Iterator<String> ids=files.keys();while(ids.hasNext()){JSONArray list=files.getJSONArray(ids.next());for(int i=0;i<list.length();i++)if(path.equals(list.getJSONObject(i).optString("path")))list.getJSONObject(i).put("saved",true);}putMeta("message_files",files);}
    public synchronized void fileMessage(String text,JSONArray attachments) throws JSONException {String id=message("assistant",text,"laptop");JSONObject old=meta("message_files",new JSONObject()),keep=new JSONObject();old.put(id,attachments);JSONArray chat=messages();for(int i=0;i<chat.length();i++){String key=chat.getJSONObject(i).getString("id");if(old.has(key))keep.put(key,old.get(key));}putMeta("message_files",keep);}
    public JSONObject snapshot(){try{JSONArray chat=messages();JSONObject files=meta("message_files",new JSONObject());for(int i=0;i<chat.length();i++){JSONObject m=chat.getJSONObject(i);if(files.has(m.getString("id")))m.put("files",files.getJSONArray(m.getString("id")));}return new JSONObject().put("settings",settings()).put("messages",chat).put("memories",memories()).put("reminders",reminders()).put("events",rows("SELECT * FROM events ORDER BY created DESC LIMIT 30")).put("focus",meta("focus",new JSONObject()));}catch(JSONException e){throw new IllegalStateException(e);}}

    public JSONObject backup() throws JSONException {
        JSONObject data=new JSONObject();
        for(String table:Arrays.asList("messages","memories","reminders","events")){
            JSONArray rows=rows("SELECT * FROM "+table+" LIMIT 10001");
            if(rows.length()>10000)throw new IllegalArgumentException("This backup is too large for the phone exporter. Your existing data is unchanged.");
            data.put(table,rows);
        }
        for(String table:Arrays.asList("focus_tasks","focus_history")){JSONArray list=rows("SELECT * FROM "+table+" LIMIT 10001");if(list.length()>10000)throw new IllegalArgumentException("Focus history is too large to export.");data.put(table,list);}
        data.put("sync_recovery",rows("SELECT kind,body,created FROM mobile_conflicts ORDER BY created DESC LIMIT 1000"));
        JSONObject result=new JSONObject().put("format","bujji-mobile").put("version",1).put("created",System.currentTimeMillis()).put("data",data);
        if(result.toString().length()>1500000)throw new IllegalArgumentException("This backup is too large for the phone importer. Your existing data is unchanged.");
        return result;
    }
    /** Merge stable IDs; never import secrets, settings, SQL or active focus sessions. */
    public void restore(JSONObject backup) throws JSONException {
        if(!backup.optString("format").equals("bujji-mobile")||backup.optInt("version")!=1)throw new IllegalArgumentException("Choose a Bujji mobile version 1 backup.");
        JSONObject data=backup.getJSONObject("data");SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{
            for(String table:Arrays.asList("messages","memories","reminders")){
                JSONArray list=data.getJSONArray(table);if(list.length()>10000)throw new IllegalArgumentException("The backup contains too many records.");
                for(int i=0;i<list.length();i++){
                    JSONObject row=list.getJSONObject(i);String id=row.getString("id");if(!UUID.fromString(id).toString().equalsIgnoreCase(id))throw new IllegalArgumentException("Invalid backup record ID");
                    ContentValues v=new ContentValues();v.put("id",id);long created=row.getLong("created");if(created<0)throw new IllegalArgumentException("Invalid backup time");v.put("created",created);
                    if(table.equals("messages")){
                        String role=row.getString("role");if(!Arrays.asList("user","assistant").contains(role))throw new IllegalArgumentException("Invalid backup role");v.put("role",role);v.put("body",Rules.bounded(row.getString("body"),8000));v.put("source","import");
                    }else{
                        long updated=row.getLong("updated");if(updated<0)throw new IllegalArgumentException("Invalid backup time");v.put("updated",updated);
                        if(table.equals("memories")){v.put("body",Rules.bounded(row.getString("body"),2000));int deleted=row.getInt("deleted");if(deleted!=0&&deleted!=1)throw new IllegalArgumentException("Invalid backup memory");v.put("deleted",deleted);}
                        else{
                            String repeat=row.getString("repeat_mode"),kind=row.getString("kind"),status=row.getString("status");
                            if(!Arrays.asList("none","daily","weekly").contains(repeat)||!Arrays.asList("reminder","focus").contains(kind)||!Arrays.asList("pending","done","cancelled").contains(status))throw new IllegalArgumentException("Invalid backup reminder");
                            long due=row.getLong("due");if(due<0||due>253402300799000L)throw new IllegalArgumentException("Invalid backup reminder time");
                            v.put("title",Rules.bounded(row.getString("title"),200));v.put("due",due);v.put("repeat_mode",repeat);v.put("kind",kind);v.put("status",kind.equals("focus")?"cancelled":status);
                        }
                    }
                    db.insertWithOnConflict(table,null,v,SQLiteDatabase.CONFLICT_IGNORE);
                }
            }
            JSONArray recovery=data.optJSONArray("sync_recovery");
            if(recovery!=null){if(recovery.length()>1000)throw new IllegalArgumentException("Too many recovery records.");for(int i=0;i<recovery.length();i++){JSONObject row=recovery.getJSONObject(i);String kind=row.getString("kind"),body=Rules.bounded(row.getString("body"),6000);long created=row.getLong("created");if(!Arrays.asList("memory","reminder").contains(kind)||created<0)throw new IllegalArgumentException("Invalid recovery record.");if(rows("SELECT id FROM mobile_conflicts WHERE kind=? AND body=? AND created=?",kind,body,Long.toString(created)).length()==0){ContentValues v=new ContentValues();v.put("kind",kind);v.put("body",body);v.put("created",created);db.insertOrThrow("mobile_conflicts",null,v);}}}
            for(String table:Arrays.asList("focus_tasks","focus_history")){JSONArray list=data.optJSONArray(table);if(list==null)continue;if(list.length()>10000)throw new IllegalArgumentException("Too many focus records.");for(int i=0;i<list.length();i++){JSONObject row=list.getJSONObject(i);String id=row.getString("id");UUID.fromString(id);ContentValues v=new ContentValues();v.put("id",id);v.put("title",Rules.bounded(row.getString("title"),200));if(table.equals("focus_tasks")){int done=row.getInt("done");long created=row.getLong("created");if((done!=0&&done!=1)||created<0)throw new IllegalArgumentException("Invalid focus task.");v.put("done",done);v.put("created",created);}else{String status=row.getString("status");long planned=row.getLong("planned"),ended=row.getLong("ended");JSONArray segments=new JSONArray(row.getString("segments"));if(!Arrays.asList("completed","ended","reset").contains(status)||planned<60000||planned>10800000||ended<0||segments.length()>1000)throw new IllegalArgumentException("Invalid focus history.");long previous=0;for(int j=0;j<segments.length();j++){JSONArray part=segments.getJSONArray(j);long start=part.getLong(0),end=part.getLong(1);if(part.length()!=2||start<previous||end<start||end>ended||end-start>10800000)throw new IllegalArgumentException("Invalid focus interval.");previous=end;}v.put("status",status);v.put("planned",planned);v.put("ended",ended);v.put("segments",segments.toString());v.put("task",row.optString("task",""));}db.insertWithOnConflict(table,null,v,SQLiteDatabase.CONFLICT_IGNORE);}}
            // History is informational. Do not replay imported notification events.
            db.setTransactionSuccessful();
        }finally{db.endTransaction();}
    }

    private void syncTables(SQLiteDatabase db){
        db.execSQL("CREATE TABLE IF NOT EXISTS mobile_links(local_id TEXT,kind TEXT,remote_id TEXT UNIQUE,revision INTEGER,baseline TEXT,PRIMARY KEY(local_id,kind))");
        db.execSQL("CREATE TABLE IF NOT EXISTS mobile_conflicts(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,body TEXT,created INTEGER)");
    }
    JSONObject syncPayload(String kind,JSONObject row) throws JSONException {
        if(kind.equals("memory"))return new JSONObject().put("body",row.getString("body")).put("deleted",row.optInt("deleted")!=0);
        return new JSONObject().put("title",row.getString("title")).put("due",row.getLong("due")).put("repeat",row.getString("repeat_mode")).put("status",row.getString("status"));
    }
    JSONObject localRow(String kind,String id){return rows("SELECT * FROM "+(kind.equals("memory")?"memories":"reminders")+" WHERE id=?",id).optJSONObject(0);}
    /** Snapshot includes fingerprints for edits made while the HTTPS request is in flight. */
    JSONObject syncSnapshot() throws JSONException {
        JSONArray changes=new JSONArray();JSONObject captured=new JSONObject();
        for(String kind:Arrays.asList("memory","reminder")){
            JSONArray list=rows("SELECT * FROM "+(kind.equals("memory")?"memories":"reminders")+(kind.equals("reminder")?" WHERE kind='reminder'":"")+" LIMIT 1001");
            if(list.length()>1000)throw new IllegalArgumentException("This preview supports 1000 records per type.");
            for(int i=0;i<list.length();i++){
                JSONObject row=list.getJSONObject(i);String id=row.getString("id");JSONObject payload=syncPayload(kind,row);captured.put(kind+":"+id,payload.toString());
                JSONObject link=rows("SELECT * FROM mobile_links WHERE local_id=? AND kind=?",id,kind).optJSONObject(0);
                if(link==null||!payload.toString().equals(link.optString("baseline"))){
                    JSONObject change=new JSONObject(payload.toString()).put("id",link==null?id:link.getString("remote_id")).put("kind",kind).put("revision",link==null?0:link.getLong("revision"));changes.put(change);
                }
            }
        }
        if(changes.length()>500)throw new IllegalArgumentException("This preview supports up to 500 changed records per sync. Export a backup before larger migrations.");
        return new JSONObject().put("changes",changes).put("captured",captured);
    }
    private void link(String local,String kind,String remote,long revision,String baseline){ContentValues v=new ContentValues();v.put("local_id",local);v.put("kind",kind);v.put("remote_id",remote);v.put("revision",revision);v.put("baseline",baseline);getWritableDatabase().insertWithOnConflict("mobile_links",null,v,SQLiteDatabase.CONFLICT_REPLACE);}
    int mergeSync(JSONObject response,JSONObject snapshot) throws JSONException {
        if(response.getInt("protocol")!=1)throw new IllegalArgumentException("Update both apps to a compatible sync version.");
        JSONArray incoming=response.getJSONArray("records");if(incoming.length()>2500)throw new IllegalArgumentException("Sync response is too large.");
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();int conflicts=0;
        try{
            JSONArray sent=snapshot.getJSONArray("changes"),results=response.getJSONArray("results");JSONObject captured=snapshot.getJSONObject("captured");
            Map<String,JSONObject> changes=new HashMap<>();for(int i=0;i<sent.length();i++)changes.put(sent.getJSONObject(i).getString("id"),sent.getJSONObject(i));
            Set<String> conflictIds=new HashSet<>();
            for(int i=0;i<results.length();i++){
                JSONObject result=results.getJSONObject(i);String remote=result.getString("id");JSONObject c=changes.get(remote);if(c==null)throw new IllegalArgumentException("Unexpected sync result.");
                if(result.optString("status").equals("conflict"))conflictIds.add(remote);
                if(result.optString("status").equals("duplicate")){
                    String kind=c.getString("kind"),local=remote;JSONObject old=rows("SELECT local_id FROM mobile_links WHERE remote_id=?",remote).optJSONObject(0);if(old!=null)local=old.getString("local_id");
                    link(local,kind,result.getString("remote_id"),0,"");
                }
            }
            for(int i=0;i<incoming.length();i++){
                JSONObject r=incoming.getJSONObject(i),p=r.getJSONObject("payload");String remote=r.getString("id"),kind=r.getString("kind");UUID.fromString(remote);if(!Arrays.asList("memory","reminder").contains(kind)||r.getLong("revision")<1)throw new IllegalArgumentException("Invalid shared record.");
                JSONObject existingLink=rows("SELECT * FROM mobile_links WHERE remote_id=?",remote).optJSONObject(0);String local=existingLink==null?remote:existingLink.getString("local_id");JSONObject old=localRow(kind,local);JSONObject canonical;
                if(kind.equals("memory"))canonical=new JSONObject().put("body",Rules.bounded(p.getString("body"),2000)).put("deleted",p.getBoolean("deleted"));
                else{
                    String repeat=p.getString("repeat"),status=p.getString("status");long due=p.getLong("due");if(!Arrays.asList("none","daily","weekly").contains(repeat)||!Arrays.asList("pending","done","cancelled").contains(status)||due<0||due>253402300799000L)throw new IllegalArgumentException("Invalid shared reminder.");
                    canonical=new JSONObject().put("title",Rules.bounded(p.getString("title"),200)).put("due",due).put("repeat",repeat).put("status",status);
                }
                String baseline=canonical.toString();String current=old==null?null:syncPayload(kind,old).toString();String before=captured.optString(kind+":"+local,null);
                boolean changedDuringRequest=current!=null&&before!=null&&!current.equals(before);
                if(changedDuringRequest){link(local,kind,remote,r.getLong("revision"),baseline);continue;}
                if(old!=null&&conflictIds.contains(remote)&&!current.equals(baseline)){
                    ContentValues copy=new ContentValues();copy.put("kind",kind);copy.put("body",current);copy.put("created",System.currentTimeMillis());db.insertOrThrow("mobile_conflicts",null,copy);conflicts++;
                }
                long now=System.currentTimeMillis();ContentValues values=new ContentValues();values.put("id",local);values.put("updated",now);
                if(kind.equals("memory")){values.put("body",canonical.getString("body"));values.put("deleted",canonical.getBoolean("deleted")?1:0);}
                else{values.put("title",canonical.getString("title"));values.put("due",canonical.getLong("due"));values.put("repeat_mode",canonical.getString("repeat"));values.put("status",canonical.getString("status"));values.put("kind","reminder");}
                if(old==null){values.put("created",now);db.insertOrThrow(kind.equals("memory")?"memories":"reminders",null,values);}else db.update(kind.equals("memory")?"memories":"reminders",values,"id=?",new String[]{local});
                link(local,kind,remote,r.getLong("revision"),baseline);
            }
            db.setTransactionSuccessful();return conflicts;
        }finally{db.endTransaction();}
    }
    void clearSyncLinks(){getWritableDatabase().delete("mobile_links",null,null);}
}
