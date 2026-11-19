package org.bujji.companion;

import android.content.*;
import android.security.keystore.*;
import android.util.Base64;
import java.security.KeyStore;
import java.util.Arrays;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** Android Keystore AES-GCM; no plaintext key fallback or key read-back to JS. */
final class SecretVault {
    private final android.content.SharedPreferences prefs;
    SecretVault(Context c){prefs=c.getSharedPreferences("encrypted-provider-keys",Context.MODE_PRIVATE);}
    private javax.crypto.SecretKey key() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias("bujji-provider-v1")){
            KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            gen.init(new KeyGenParameterSpec.Builder("bujji-provider-v1",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());gen.generateKey();
        }
        return (javax.crypto.SecretKey)ks.getKey("bujji-provider-v1",null);
    }
    boolean has(String provider){return prefs.contains(provider);}
    void save(String provider,String value) throws Exception {
        if(!AIRouting.PROVIDERS.contains(provider)&&!provider.equals("laptop"))throw new IllegalArgumentException("Unknown provider");
        value=value.trim().replaceFirst("^(GEMINI_API_KEY|GROQ_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|PERPLEXITY_API_KEY)\\s*=\\s*","");
        if(value.length()<20||value.length()>1000||value.matches("(?s).*\\s.*"))throw new IllegalArgumentException("Paste only the API key value, without spaces.");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());byte[] data=cipher.doFinal(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));byte[] iv=cipher.getIV();byte[] all=new byte[iv.length+data.length];System.arraycopy(iv,0,all,0,iv.length);System.arraycopy(data,0,all,iv.length,data.length);
        if(!prefs.edit().putString(provider,Base64.encodeToString(all,Base64.NO_WRAP)).commit())throw new IllegalStateException("The key could not be saved.");
    }
    String get(String provider) throws Exception {
        String stored=prefs.getString(provider,null);if(stored==null)throw new IllegalArgumentException("Add a model and API key in Settings first.");
        byte[] all=Base64.decode(stored,Base64.NO_WRAP);if(all.length<29)throw new IllegalStateException("Reconnect this provider; its saved key could not be read.");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Arrays.copyOfRange(all,0,12)));
        return new String(cipher.doFinal(Arrays.copyOfRange(all,12,all.length)),java.nio.charset.StandardCharsets.UTF_8);
    }
    void clear(String provider){if(!prefs.edit().remove(provider).commit())throw new IllegalStateException("The key could not be removed.");}
}
