package org.bujji.companion;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class AIRoutingTest {
 @Test public void autoTasksAndManualOverride(){String[][] cases={{"explain DBMS","study"},{"debug python","coding"},{"latest news sources","research"},{"draft an email","writing"},{"calculate budget","analysis"},{"hello","daily"},{"chocolate","daily"},{"find latest PDF in Downloads","daily"},{"dbms nerpinchu","study"}};for(String[] c:cases){assertEquals(c[0],c[1],AIRouting.task("auto",c[0]));assertEquals("daily",AIRouting.task("daily",c[0]));}}
 @Test public void modelMigrationKeepsLegacyVoice() throws Exception {JSONObject s=new JSONObject().put("provider","gemini").put("model","legacy-audio-model");assertEquals("legacy-audio-model",AIRouting.model(s,"gemini"));assertEquals("gemini",AIRouting.speech(s));assertEquals("gemini",AIRouting.routes(s).getString("study"));assertEquals("gemini",AIRouting.routes(s).getString("research"));s.put("models",AIRouting.models(s));s.put("speechProvider","gemini");s.put("provider","anthropic");assertEquals("legacy-audio-model",AIRouting.model(s,"gemini"));assertEquals("gemini",AIRouting.speech(s));}
 @Test public void customRoutesAndModelsSurviveSerialization() throws Exception {JSONObject s=new JSONObject().put("provider","gemini").put("model","audio-model").put("models",new JSONObject().put("openai","chat-model"));JSONObject routes=AIRouting.routes(s);routes.put("study","anthropic");s.put("routes",routes);s=new JSONObject(s.toString());assertEquals("anthropic",AIRouting.routes(s).getString("study"));assertEquals("chat-model",AIRouting.model(s,"openai"));assertEquals("audio-model",AIRouting.model(s,"gemini"));}
 @Test public void claudeParserOnlyReturnsText() throws Exception {assertEquals("Hello",Cloud.claudeText(new JSONObject("{\"content\":[{\"type\":\"thinking\",\"thinking\":\"hidden\"},{\"type\":\"text\",\"text\":\"Hello\"}]}")));}
 @Test public void researchSourcesAreReturnedAndFiltered() throws Exception {String answer=Cloud.researchText(new JSONObject("{\"output\":[{\"type\":\"search_results\",\"results\":[{\"url\":\"https://example.org/source\"},{\"url\":\"javascript:alert(1)\"}]},{\"type\":\"message\",\"content\":[{\"type\":\"output_text\",\"text\":\"Answer\",\"annotations\":[{\"url\":\"https://example.org/source\"}]}]}]}"));assertTrue(answer.startsWith("Answer"));assertTrue(answer.contains("Sources:"));assertFalse(answer.contains("javascript:"));assertEquals(answer.indexOf("https://example.org/source"),answer.lastIndexOf("https://example.org/source"));}
 @Test public void emptyResearchIsNotClaimedSuccessful() throws Exception {try{Cloud.researchText(new JSONObject().put("output",new JSONArray()));fail("Empty result accepted");}catch(java.io.IOException expected){}}
}
