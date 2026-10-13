package com.attijariwafa.titres.perf.data;

/**
 * Client references of a campaign: {@code PERF-<campaignId>-<user>-<seq>}. With
 * {@code source = PERF} this is the key every order of a run is found by in ORDERS
 * (unique index on source + client reference) and in the ledger.
 */
public final class CampaignRefs {

    private CampaignRefs() {
    }

    public static String prefix(String campaignId) {
        return "PERF-" + campaignId + "-";
    }

    public static String clientReference(String campaignId, long userIndex, long sequence) {
        return prefix(campaignId) + userIndex + "-" + sequence;
    }
}
