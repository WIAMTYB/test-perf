package com.attijariwafa.titres.perf.protocol;

import com.attijariwafa.titres.perf.config.PerfConfig;
import io.gatling.javaapi.http.HttpProtocolBuilder;

import static io.gatling.javaapi.http.HttpDsl.http;

/**
 * The selfcare client API as the mobile application speaks it: API key header, JSON, gzip
 * accepted, one connection pool per virtual user (no shared connections), no caching.
 */
public final class SelfcareProtocol {

    private SelfcareProtocol() {
    }

    public static HttpProtocolBuilder selfcare() {
        PerfConfig config = PerfConfig.get();
        return http.baseUrl(config.baseUrl())
                .header("X-Api-Key", config.apiKey())
                .acceptHeader("application/json")
                .acceptEncodingHeader("gzip")
                .contentTypeHeader("application/json")
                .userAgentHeader("titres-trading-performance-tests/1.0 (" + config.campaignId() + ")")
                .disableCaching()
                .disableFollowRedirect();
    }
}
