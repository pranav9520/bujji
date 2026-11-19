package org.bujji.companion;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.Config;
import java.io.*;
import java.util.Arrays;
import static org.junit.Assert.*;
@RunWith(RobolectricTestRunner.class) @Config(sdk=28)
public class RemoteDownloadTest {
 @Test public void copiesBytesWithoutLoadingEntireFile() throws Exception {byte[] data="Assignment PDF content".getBytes("UTF-8");ByteArrayOutputStream out=new ByteArrayOutputStream();DeviceSync.copyDownload(new ByteArrayInputStream(data),out,data.length);assertArrayEquals(data,out.toByteArray());}
 @Test public void rejectsTruncatedTransfers() throws Exception {try{DeviceSync.copyDownload(new ByteArrayInputStream(new byte[3]),new ByteArrayOutputStream(),10);fail("Truncated transfer accepted");}catch(IOException expected){assertTrue(expected.getMessage().contains("Incomplete"));}}
 @Test public void rejectsOversizeHeadersBeforeWriting() throws Exception {ByteArrayOutputStream out=new ByteArrayOutputStream();try{DeviceSync.copyDownload(new ByteArrayInputStream(new byte[3]),out,25*1024*1024+1);fail("Oversize header accepted");}catch(IOException expected){assertEquals(0,out.size());}}
 @Test public void limitsUnknownLengthStreams() throws Exception {InputStream in=new InputStream(){int remaining=25*1024*1024+1;public int read(){return remaining-->0?1:-1;}public int read(byte[] b,int off,int len){if(remaining<=0)return -1;int n=Math.min(len,remaining);Arrays.fill(b,off,off+n,(byte)1);remaining-=n;return n;}};OutputStream out=new OutputStream(){public void write(int b){}public void write(byte[] b,int off,int len){}};try{DeviceSync.copyDownload(in,out,-1);fail("Unlimited stream accepted");}catch(IOException expected){assertTrue(expected.getMessage().contains("25 MB"));}}
}
