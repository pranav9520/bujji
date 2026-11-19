package org.bujji.companion;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class MainActivityTest {
 @Test public void launchAndBackgroundDoNotRequireAKeyOrLaptop(){
  try(org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create().start().resume().visible()){
   assertNotNull(controller.get().findViewById(android.R.id.content));
   controller.pause().stop();
  }
 }
}
