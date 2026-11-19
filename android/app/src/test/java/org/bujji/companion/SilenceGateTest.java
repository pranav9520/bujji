package org.bujji.companion;
import org.junit.Test;
import static org.junit.Assert.*;
public class SilenceGateTest {
 @Test public void quietStopsAtThreeSeconds(){SilenceGate gate=new SilenceGate(100);assertFalse(gate.update(0,3099));assertTrue(gate.update(0,3100));assertFalse(gate.heard);}
 @Test public void speechResetsQuietTimer(){SilenceGate gate=new SilenceGate(0);assertFalse(gate.update(1000,2900));assertTrue(gate.heard);assertFalse(gate.update(0,5899));assertTrue(gate.update(0,5900));}
 @Test public void continuousSpeechKeepsTwentySecondCap(){SilenceGate gate=new SilenceGate(0);for(int time=0;time<20000;time+=1000)assertFalse(gate.update(1200,time));assertTrue(gate.update(1200,20000));}
}
