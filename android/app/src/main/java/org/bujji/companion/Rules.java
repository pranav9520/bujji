package org.bujji.companion;

import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.regex.*;

/** Pure, testable intent/time rules. Nothing here executes a phone action. */
public final class Rules {
    public static final class Plan {
        public final String id=java.util.UUID.randomUUID().toString();
        public String type,title="",text="",repeat="none";public long at,duration;public long expires=System.currentTimeMillis()+300_000;
        public Plan(String type){this.type=type;}
    }
    public static Plan parse(String input,ZonedDateTime now){
        String s=input.trim();Matcher m=Pattern.compile("(?i)^remember(?: that)? (.{1,2000})$").matcher(s);
        if(m.matches()){Plan p=new Plan("memory");p.text=m.group(1).trim();return p;}
        m=Pattern.compile("(?i)^remind me(?: to (.+?))? in (\\d{1,5}) (minutes?|hours?|days?)(?: (?:to )?(.+))?[.!]?$").matcher(s);
        if(m.matches()){
            long count=Long.parseLong(m.group(2));long scale=m.group(3).toLowerCase(Locale.ROOT).startsWith("hour")?3600:m.group(3).toLowerCase(Locale.ROOT).startsWith("day")?86400:60;
            String title=m.group(1)!=null?m.group(1):m.group(4);
            if(count<1||count*scale>366L*86400||title==null||title.trim().isEmpty())throw new IllegalArgumentException("Include what to remember and a time within the next year.");
            Plan p=new Plan("reminder");p.title=title;p.at=now.toInstant().toEpochMilli()+count*scale*1000;return p;
        }
        if(s.toLowerCase(Locale.ROOT).matches("^(set |keep |create )?(an? )?alarm\\b.*")){
            Plan p=new Plan("clock");p.title="Bujji alarm";p.at=requestedTime(s,now).toInstant().toEpochMilli();return p;
        }
        m=Pattern.compile("(?i)^(?:start|begin) (?:a )?(\\d{1,3}) (?:minute|minutes|min) (?:focus|study)(?: session)?(?: (?:on|for) (.+))?[.!]?$").matcher(s);
        if(m.matches()){
            int minutes=Integer.parseInt(m.group(1));if(minutes<1||minutes>180)throw new IllegalArgumentException("Focus sessions can be 1–180 minutes.");
            Plan p=new Plan("focus");p.title=m.group(2)==null?"Focus session":m.group(2);p.duration=minutes*60_000L;return p;
        }
        if(s.toLowerCase(Locale.ROOT).matches("^(check |show |what is |what's |how much is )?(my )?screen ?time[?!.]?$"))return new Plan("usage");
        return null;
    }
    public static ZonedDateTime requestedTime(String text,ZonedDateTime now){
        Matcher m=Pattern.compile("(?i)\\b(\\d{1,2})(?::([0-5]\\d))?\\s*(am|pm)\\b|\\b([01]\\d|2[0-3]):([0-5]\\d)\\b").matcher(text);
        if(!m.find())throw new IllegalArgumentException("Please include a time such as 5 AM or 17:30.");
        String rest=(text.substring(0,m.start())+" "+text.substring(m.end())).toLowerCase(Locale.ROOT).replaceAll("\\b(set|keep|create|a|an|alarm|at|for|today|tomorrow)\\b", " ").replaceAll("[\\s.!?]+", "");
        if(!rest.isEmpty())throw new IllegalArgumentException("Please use a time with today/tomorrow, or choose the exact date in the alarm form.");
        int hour,minute;
        if(m.group(4)!=null){hour=Integer.parseInt(m.group(4));minute=Integer.parseInt(m.group(5));}
        else{hour=Integer.parseInt(m.group(1));minute=m.group(2)==null?0:Integer.parseInt(m.group(2));if(hour<1||hour>12)throw new IllegalArgumentException("Use 1–12 with AM/PM.");hour=hour%12+(m.group(3).equalsIgnoreCase("pm")?12:0);}
        LocalDate day=now.toLocalDate();boolean tomorrow=text.toLowerCase(Locale.ROOT).contains("tomorrow");
        if(tomorrow)day=day.plusDays(1);
        ZonedDateTime result=day.atTime(hour,minute).atZone(now.getZone());
        if(!result.isAfter(now)){if(text.toLowerCase(Locale.ROOT).contains("today"))throw new IllegalArgumentException("That time today has already passed.");result=result.plusDays(1);}
        return result;
    }
    public static long nextDue(long due,String repeat,long now,ZoneId zone){
        if(repeat.equals("none"))return -1;
        if(!repeat.equals("daily")&&!repeat.equals("weekly"))throw new IllegalArgumentException("Unknown repeat setting.");
        ZonedDateTime initial=Instant.ofEpochMilli(due).atZone(zone);int step=repeat.equals("daily")?1:7;
        long days=Math.max(step,java.time.temporal.ChronoUnit.DAYS.between(initial.toLocalDate(),Instant.ofEpochMilli(now).atZone(zone).toLocalDate())/step*step);
        ZonedDateTime next=initial.plusDays(days);if(next.toInstant().toEpochMilli()<=now)next=next.plusDays(step);
        return next.toInstant().toEpochMilli();
    }
    public static boolean clockCanExpress(long at,ZonedDateTime now){
        ZonedDateTime wanted=Instant.ofEpochMilli(at).atZone(now.getZone());ZonedDateTime next=now.toLocalDate().atTime(wanted.toLocalTime()).atZone(now.getZone());
        if(!next.isAfter(now))next=next.plusDays(1);return next.toLocalDate().equals(wanted.toLocalDate());
    }
    public static void future(long at){long delta=at-System.currentTimeMillis();if(delta<1000||delta>366L*86400_000)throw new IllegalArgumentException("Choose a future time within the next year.");}
    public static String bounded(String value,int max){String result=value==null?"":value.trim();if(result.isEmpty()||result.length()>max)throw new IllegalArgumentException("Please use 1–"+max+" characters.");return result;}
    public static String label(long at){return Instant.ofEpochMilli(at).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("EEE, d MMM · h:mm a",Locale.ENGLISH));}
    private Rules(){}
}
