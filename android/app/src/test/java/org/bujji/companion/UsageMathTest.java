package org.bujji.companion;
import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;
public class UsageMathTest {
 private UsageMath.Event e(long at,int type,String app){return new UsageMath.Event(at,type,app,app);}
 @Test public void overlappingAppsCountOnce(){UsageMath.Result r=UsageMath.compute(Arrays.asList(e(0,1,"a"),e(10,1,"b"),e(20,2,"b"),e(30,2,"a")),0,40);assertEquals(30,r.total);assertEquals(Long.valueOf(20),r.apps.get("a"));assertEquals(Long.valueOf(10),r.apps.get("b"));}
 @Test public void midnightCarryOnlyCountsToday(){assertEquals(20,UsageMath.compute(Arrays.asList(e(80,1,"a"),e(120,2,"a")),100,200).total);}
 @Test public void screenOffStopsCounting(){assertEquals(10,UsageMath.compute(Arrays.asList(e(0,1,"a"),e(10,3,""),e(50,4,"")),0,100).total);}
 @Test public void ongoingSessionCountsUntilNow(){assertEquals(70,UsageMath.compute(Arrays.asList(e(30,1,"a")),0,100).total);}
 @Test public void futureEventsNotCounted(){assertEquals(0,UsageMath.compute(Arrays.asList(e(200,1,"a")),0,100).total);}
 @Test public void emptyEventsZero(){assertEquals(0,UsageMath.compute(Collections.emptyList(),0,100).total);}
 @Test public void quietHoursCrossMidnight(){assertTrue(UsageMath.quiet(23,22,7));assertTrue(UsageMath.quiet(6,22,7));assertFalse(UsageMath.quiet(7,22,7));assertFalse(UsageMath.quiet(12,22,7));}
 @Test public void equalQuietHoursDisableQuiet(){assertFalse(UsageMath.quiet(12,0,0));}
 @Test public void nudgeThresholdCooldownAndCap(){assertTrue(UsageMath.shouldNudge(480,480,false,0,0,10000000,60));assertFalse(UsageMath.shouldNudge(479,480,false,0,0,10000000,60));assertFalse(UsageMath.shouldNudge(500,480,true,0,0,10000000,60));assertFalse(UsageMath.shouldNudge(500,480,false,3,0,10000000,60));assertFalse(UsageMath.shouldNudge(500,480,false,1,9999999,10000000,60));}
}
