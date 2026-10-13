package com.attijariwafa.titres.perf.config;

import java.net.URI;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Refuses to run a campaign anywhere but the test environments, with any order source but
 * PERF, or without a well-formed campaign id. Production can never be a target: there is no
 * profile for it and the host allowlist would reject it anyway.
 */
public final class EnvGuard {

    static final List<String> ALLOWED_HOST_SUFFIXES = List.of(
            ".apps.ocpdev.attijariwafa.net",
            ".apps.ocppprd.attijariwafa.net");

    static final Pattern CAMPAIGN_ID = Pattern.compile("[A-Z0-9-]{4,24}");

    private EnvGuard() {
    }

    static void verify(PerfConfig config) {
        String baseUrl = config.optional("selfcare.baseUrl").orElse("");
        String host = URI.create(baseUrl).getHost();
        if (host == null || ALLOWED_HOST_SUFFIXES.stream().noneMatch(host::endsWith)) {
            throw new IllegalStateException("Refusing to target '" + baseUrl + "': host is not a recette or preprod route");
        }
        String source = config.optional("orders.source").orElse("");
        if (!"PERF".equals(source)) {
            throw new IllegalStateException("Refusing to book orders with source '" + source + "': campaigns must use PERF");
        }
        config.optional("perf.campaignId").ifPresent(id -> {
            if (!CAMPAIGN_ID.matcher(id).matches()) {
                throw new IllegalStateException("Campaign id '" + id + "' must match " + CAMPAIGN_ID.pattern());
            }
        });
    }

    /** The same checks on plain values, for the unit tests and the harness mirror. */
    public static boolean allowedHost(String host) {
        return host != null && ALLOWED_HOST_SUFFIXES.stream().anyMatch(host::endsWith);
    }

    public static boolean validCampaignId(String id) {
        return id != null && CAMPAIGN_ID.matcher(id).matches();
    }
}
