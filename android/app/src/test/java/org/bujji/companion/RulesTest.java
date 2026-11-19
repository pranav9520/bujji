package org.bujji.companion;
import org.junit.Test;
import java.time.*;
import static org.junit.Assert.*;
public class RulesTest {
 private final ZonedDateTime now=ZonedDateTime.of(2026,11,18,14,0,0,0,ZoneId.of("Asia/Kolkata"));
 @Test public void relativeReminderHasExplicitSubject(){Rules.Plan p=Rules.parse("Remind me in 10 minutes to study",now);assertEquals("reminder",p.type);assertEquals("study",p.title);assertEquals(now.toInstant().toEpochMilli()+600000,p.at);}
 @Test public void reminderAlternateOrder(){assertEquals("drink water",Rules.parse("Remind me to drink water in 2 hours",now).title);}
 @Test(expected=IllegalArgumentException.class) public void ambiguousReminderCannotRun(){Rules.parse("remind me in 5 minutes",now);}
 @Test(expected=IllegalArgumentException.class) public void zeroReminderRejected(){Rules.parse("remind me in 0 minutes to study",now);}
 @Test public void memoryIsOnlyAProposal(){Rules.Plan p=Rules.parse("remember that I like tea",now);assertEquals("memory",p.type);assertEquals("I like tea",p.text);assertTrue(p.expires>System.currentTimeMillis());}
 @Test public void unknownTaskNeedsModel(){assertNull(Rules.parse("Find my assignment on the laptop",now));}
 @Test public void tomorrowClock(){assertEquals(now.toLocalDate().plusDays(1).atTime(5,0),Rules.requestedTime("set an alarm at 5 AM tomorrow",now).toLocalDateTime());}
 @Test(expected=IllegalArgumentException.class) public void unsupportedClockDateIsNotGuessed(){Rules.requestedTime("alarm next Friday at 5 am",now);}
 @Test public void noonAndMidnight(){assertEquals(12,Rules.requestedTime("alarm at 12 pm",now).getHour());assertEquals(0,Rules.requestedTime("alarm at 12 am",now).getHour());}
 @Test(expected=IllegalArgumentException.class) public void pastTodayRejected(){Rules.requestedTime("alarm at 5 am today",now);}
 @Test public void clockArbitraryDateCannotBeSilentlyPassed(){assertFalse(Rules.clockCanExpress(now.plusDays(2).toInstant().toEpochMilli(),now));assertTrue(Rules.clockCanExpress(now.plusHours(1).toInstant().toEpochMilli(),now));}
 @Test public void localFocusDuration(){Rules.Plan p=Rules.parse("start a 25 minute study session on DBMS",now);assertEquals("DBMS",p.title);assertEquals(1500000,p.duration);}
 @Test(expected=IllegalArgumentException.class) public void focusBounded(){Rules.parse("start a 999 minute focus",now);}
 @Test public void missedRepeatsSkipPastOccurrences(){long next=Rules.nextDue(now.toInstant().toEpochMilli(),"daily",now.plusDays(4).plusHours(1).toInstant().toEpochMilli(),now.getZone());assertEquals(now.plusDays(5).toInstant().toEpochMilli(),next);}
 @Test public void manualEarlyRepeatAdvances(){assertEquals(now.plusDays(7).toInstant().toEpochMilli(),Rules.nextDue(now.toInstant().toEpochMilli(),"weekly",now.minusHours(1).toInstant().toEpochMilli(),now.getZone()));}
 @Test public void repeatingWallTimeSurvivesDst(){ZoneId zone=ZoneId.of("America/New_York");ZonedDateTime due=ZonedDateTime.of(2026,3,7,9,0,0,0,zone);long next=Rules.nextDue(due.toInstant().toEpochMilli(),"daily",due.toInstant().toEpochMilli(),zone);assertEquals(9,Instant.ofEpochMilli(next).atZone(zone).getHour());assertEquals(23*3600000L,next-due.toInstant().toEpochMilli());}
 @Test public void nonRepeatingEnds(){assertEquals(-1,Rules.nextDue(1,"none",2,now.getZone()));}
 @Test(expected=IllegalArgumentException.class) public void emptyMemoryRejected(){Rules.bounded("  ",20);}
}
