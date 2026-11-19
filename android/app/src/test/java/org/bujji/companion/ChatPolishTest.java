package org.bujji.companion;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import org.json.*;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class ChatPolishTest {
 @Test public void fileIntentsDoNotStealInformationalQuestions(){assertTrue(MainActivity.laptopFilesIntent("Send my assignment PDF from Downloads"));assertTrue(MainActivity.laptopFilesIntent("Find notes on my laptop"));assertTrue(MainActivity.laptopFilesIntent("download photo.jpg"));assertTrue(MainActivity.laptopFilesIntent("open my assignment PDF"));assertTrue(MainActivity.laptopFilesIntent("show Downloads"));assertFalse(MainActivity.laptopFilesIntent("Explain what a PDF file is"));assertFalse(MainActivity.laptopFilesIntent("write code to read a file"));}
 @Test public void shortRepliesAreBriefWithoutTaskRedirect(){String instruction=Cloud.shortInstructions();assertTrue(instruction.contains("never redirect informational questions"));assertFalse(instruction.contains("Ask the user to use Chat"));String result=Cloud.shortAnswer("word ".repeat(200));assertTrue(result.length()<400);assertTrue(result.endsWith("…"));}
 @Test public void attachmentCardsPersistWithoutEnteringModelContext() throws Exception {android.content.Context c=RuntimeEnvironment.getApplication();c.deleteDatabase("bujji-mobile.sqlite3");Store s=new Store(c);s.fileMessage("Found notes",new JSONArray().put(new JSONObject().put("path","C:\\Downloads\\notes.pdf").put("name","notes.pdf")));assertEquals("notes.pdf",s.snapshot().getJSONArray("messages").getJSONObject(0).getJSONArray("files").getJSONObject(0).getString("name"));s.markFileSaved("C:\\Downloads\\notes.pdf");s.close();s=new Store(c);assertTrue(s.snapshot().getJSONArray("messages").getJSONObject(0).has("files"));assertTrue(s.snapshot().getJSONArray("messages").getJSONObject(0).getJSONArray("files").getJSONObject(0).getBoolean("saved"));assertFalse(s.context().toString().contains("Downloads"));s.close();c.deleteDatabase("bujji-mobile.sqlite3");}
 @Test public void saveFilenameDoesNotRequireAnExactDestination(){assertEquals("notes.pdf",DeviceSync.filename("C:\\Users\\Test\\Downloads\\notes.pdf"));try{DeviceSync.filename("C:\\Downloads\\");fail();}catch(IllegalArgumentException expected){}}
}
