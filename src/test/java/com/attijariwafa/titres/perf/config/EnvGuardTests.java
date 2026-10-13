package com.attijariwafa.titres.perf.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class EnvGuardTests {

    @Test
    void onlyTheTestClustersAreAllowed() {
        assertThat(EnvGuard.allowedHost("recette-api-titres-selfcare-services.apps.ocpdev.attijariwafa.net")).isTrue();
        assertThat(EnvGuard.allowedHost("api-titres-selfcare-services.apps.ocppprd.attijariwafa.net")).isTrue();
        assertThat(EnvGuard.allowedHost("api-titres-selfcare.attijariwafa.net")).isFalse();
        assertThat(EnvGuard.allowedHost("apps.ocpprd.attijariwafa.net")).isFalse();
        assertThat(EnvGuard.allowedHost(null)).isFalse();
    }

    @Test
    void campaignIdsAreShortUpperCaseTokens() {
        assertThat(EnvGuard.validCampaignId("SMOKE-20261015A")).isTrue();
        assertThat(EnvGuard.validCampaignId("RCT-42")).isTrue();
        assertThat(EnvGuard.validCampaignId("abc")).isFalse();
        assertThat(EnvGuard.validCampaignId("with space")).isFalse();
        assertThat(EnvGuard.validCampaignId("TOO-LONG-CAMPAIGN-IDENTIFIER-1")).isFalse();
    }
}
