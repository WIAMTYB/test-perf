package com.attijariwafa.titres.perf.support;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.atomic.AtomicLong;

/**
 * What every simulation shares: the seeded random source (one per JVM, so a run with the
 * same seed, data files and parameters draws the same instruments in the same order), the
 * virtual-user counter behind the client references, and the {@code campaign.json} record.
 */
public final class CampaignContext {

    private static final Random RANDOM = new Random(PerfConfig.get().seed());
    private static final AtomicLong USERS = new AtomicLong();
    private static final AtomicLong SEQUENCE = new AtomicLong();

    private CampaignContext() {
    }

    public static synchronized int nextInt(int bound) {
        return RANDOM.nextInt(bound);
    }

    public static long nextUserIndex() {
        return USERS.incrementAndGet();
    }

    public static long nextSequence() {
        return SEQUENCE.incrementAndGet();
    }

    /** Writes {@code campaign.json} next to the ledger, before the first request. */
    public static void start(String simulation) {
        PerfConfig config = PerfConfig.get();
        try {
            Files.createDirectories(config.runDir());
            Map<String, Object> record = new LinkedHashMap<>();
            record.put("campaignId", config.campaignId());
            record.put("simulation", simulation);
            record.put("env", config.env());
            record.put("baseUrl", config.baseUrl());
            record.put("startedAt", Instant.now().toString());
            record.put("seed", config.seed());
            record.put("duration", config.duration().toString());
            record.put("targetRate", config.targetRate().orElse(null));
            record.put("users", config.users().orElse(null));
            record.put("profile", config.profile());
            record.put("side", config.side());
            record.put("cancelAfterSubmission", config.cancelAfterSubmission());
            record.put("maxOrders", config.maxOrders());
            record.put("instruments", InstrumentCatalog.instruments());
            record.put("parameters", config.publicParameters());
            record.put("gatlingVersion", gatlingVersion());
            record.put("javaVersion", System.getProperty("java.version"));
            ObjectMapper mapper = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT);
            Files.writeString(config.runDir().resolve("campaign.json"), mapper.writeValueAsString(record), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new IllegalStateException("Cannot write campaign.json in " + config.runDir(), e);
        }
    }

    /** Appends the end of the run to {@code campaign.json}'s sibling {@code campaign-end.json}. */
    public static void end() {
        PerfConfig config = PerfConfig.get();
        Path file = config.runDir().resolve("campaign-end.json");
        try {
            Map<String, Object> record = new LinkedHashMap<>();
            record.put("endedAt", Instant.now().toString());
            record.put("ordersBooked", AbortGuard.ordersBooked());
            record.put("aborted", AbortGuard.abortRequested());
            Files.writeString(file, new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT).writeValueAsString(record), StandardCharsets.UTF_8);
        } catch (IOException e) {
            System.err.println("[perf] cannot write " + file + ": " + e.getMessage());
        }
    }

    private static String gatlingVersion() {
        Package pkg = io.gatling.javaapi.core.Simulation.class.getPackage();
        return pkg != null && pkg.getImplementationVersion() != null ? pkg.getImplementationVersion() : "unknown";
    }
}
