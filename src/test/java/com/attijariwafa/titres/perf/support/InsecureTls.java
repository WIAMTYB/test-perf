package com.attijariwafa.titres.perf.support;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.security.KeyManagementException;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;

/**
 * Trust-all SSL context for the few plain {@link java.net.http.HttpClient} calls made outside
 * Gatling (instrument catalog). The test routes carry internal-CA certificates and the hosts
 * are allowlisted by {@code EnvGuard}, so the trust decision is already made there.
 */
public final class InsecureTls {

    private InsecureTls() {
    }

    public static SSLContext context() {
        try {
            SSLContext context = SSLContext.getInstance("TLS");
            context.init(null, new TrustManager[]{new X509TrustManager() {
                @Override
                public void checkClientTrusted(X509Certificate[] chain, String authType) {
                }

                @Override
                public void checkServerTrusted(X509Certificate[] chain, String authType) {
                }

                @Override
                public X509Certificate[] getAcceptedIssuers() {
                    return new X509Certificate[0];
                }
            }}, new SecureRandom());
            return context;
        } catch (NoSuchAlgorithmException | KeyManagementException e) {
            throw new IllegalStateException("Cannot build the SSL context", e);
        }
    }
}
