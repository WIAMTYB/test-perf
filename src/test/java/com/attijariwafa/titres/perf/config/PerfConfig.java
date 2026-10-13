package com.attijariwafa.titres.perf.config;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Properties;

/**
 * Campaign configuration, resolved once per JVM.
 *
 * <p>Resolution order, highest first: {@code -Dperf.*} system properties, {@code PERF_*}
 * environment variables, the project {@code .env} file (parsed here, never sourced), then the
 * committed profile {@code profiles/<env>.properties}. Secrets only ever come from the first
 * three and are never printed.
 */
public final class PerfConfig {

    private static final PerfConfig INSTANCE = load();

    private final Map<String, String> values;
    private final Path projectDir;

    private PerfConfig(Map<String, String> values, Path projectDir) {
        this.values = values;
        this.projectDir = projectDir;
    }

    public static PerfConfig get() {
        return INSTANCE;
    }

    private static PerfConfig load() {
        Path projectDir = Path.of(System.getProperty("perf.projectDir", System.getProperty("user.dir")))
                .toAbsolutePath().normalize();
        Map<String, String> dotEnv = readDotEnv(projectDir.resolve(".env"));

        String env = firstNonBlank(System.getProperty("perf.env"), System.getenv("PERF_ENV"), dotEnv.get("PERF_ENV"), "recette");
        Map<String, String> values = new HashMap<>(readProfile(env));
        values.put("perf.env", env);

        // Secrets and overrides from the .env file, then the real environment, then -D.
        copy(dotEnv, values);
        copy(System.getenv(), values);
        System.getProperties().forEach((k, v) -> {
            String key = k.toString();
            if (key.startsWith("perf.") && v != null && !v.toString().isBlank()) {
                values.put(key, v.toString());
            }
        });
        PerfConfig config = new PerfConfig(values, projectDir);
        EnvGuard.verify(config);
        return config;
    }

    /** Maps the PERF_* variables onto their property names. */
    private static void copy(Map<String, String> source, Map<String, String> target) {
        for (Map.Entry<String, String> entry : source.entrySet()) {
            String key = entry.getKey();
            String value = entry.getValue();
            if (value == null || value.isBlank()) {
                continue;
            }
            switch (key) {
                case "PERF_API_KEY" -> target.put("secret.apiKey", value);
                case "PERF_METRICS_API_KEY" -> target.put("secret.metricsApiKey", value);
                case "PERF_CAMPAIGN_ID" -> target.put("perf.campaignId", value);
                case "PERF_SEED" -> target.put("perf.seed", value);
                case "PERF_RUN_DIR" -> target.put("perf.runDir", value);
                default -> {
                    // Other PERF_* variables are harness-only.
                }
            }
        }
    }

    private static Map<String, String> readProfile(String env) {
        String resource = "profiles/" + env + ".properties";
        try (InputStream in = PerfConfig.class.getClassLoader().getResourceAsStream(resource)) {
            if (in == null) {
                throw new IllegalStateException("Unknown environment '" + env + "': no " + resource + " on the classpath");
            }
            Properties properties = new Properties();
            properties.load(in);
            Map<String, String> map = new HashMap<>();
            properties.forEach((k, v) -> map.put(k.toString(), v.toString().trim()));
            return map;
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read " + resource, e);
        }
    }

    static Map<String, String> readDotEnv(Path file) {
        Map<String, String> map = new HashMap<>();
        if (!Files.exists(file)) {
            return map;
        }
        try {
            for (String raw : Files.readAllLines(file, StandardCharsets.UTF_8)) {
                String line = raw.strip();
                if (line.isEmpty() || line.startsWith("#") || !line.contains("=")) {
                    continue;
                }
                int eq = line.indexOf('=');
                String key = line.substring(0, eq).strip();
                String value = line.substring(eq + 1).strip();
                if (value.length() >= 2 && (value.startsWith("\"") && value.endsWith("\"") || value.startsWith("'") && value.endsWith("'"))) {
                    value = value.substring(1, value.length() - 1);
                }
                map.put(key, value);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read " + file, e);
        }
        return map;
    }

    private static String firstNonBlank(String... candidates) {
        for (String candidate : candidates) {
            if (candidate != null && !candidate.isBlank()) {
                return candidate;
            }
        }
        return null;
    }

    // --- raw access ------------------------------------------------------------

    public String require(String key) {
        String value = values.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Missing configuration '" + key + "' (profile " + env() + ")");
        }
        return value;
    }

    public Optional<String> optional(String key) {
        String value = values.get(key);
        return value == null || value.isBlank() ? Optional.empty() : Optional.of(value);
    }

    public int intValue(String key, int fallback) {
        return optional(key).map(Integer::parseInt).orElse(fallback);
    }

    public double doubleValue(String key, double fallback) {
        return optional(key).map(Double::parseDouble).orElse(fallback);
    }

    // --- typed getters -----------------------------------------------------------

    public String env() {
        return values.get("perf.env");
    }

    public Path projectDir() {
        return projectDir;
    }

    public String baseUrl() {
        return require("selfcare.baseUrl");
    }

    /** The client API key; required for every simulation. */
    public String apiKey() {
        String key = values.get("secret.apiKey");
        if (key == null || key.isBlank()) {
            throw new IllegalStateException("PERF_API_KEY is not set (environment or .env)");
        }
        return key;
    }

    public String campaignId() {
        return require("perf.campaignId");
    }

    public long seed() {
        return Long.parseLong(optional("perf.seed").orElse("20261009"));
    }

    public Duration duration() {
        return Duration.parse(optional("perf.duration").orElse("PT10M"));
    }

    public Optional<Double> targetRate() {
        return optional("perf.targetRate").map(Double::parseDouble);
    }

    public Optional<Integer> users() {
        return optional("perf.users").map(Integer::parseInt);
    }

    public String profile() {
        return optional("perf.profile").orElse("nominal").toLowerCase(Locale.ROOT);
    }

    public String side() {
        return optional("perf.side").orElse("BUY").toUpperCase(Locale.ROOT);
    }

    public boolean cancelAfterSubmission() {
        return Boolean.parseBoolean(optional("perf.cancel").orElse("false"));
    }

    /** Where the ledger and the ABORT flag live; the harness passes the campaign directory. */
    public Path runDir() {
        return optional("perf.runDir").map(Path::of).orElse(projectDir.resolve("target").resolve("perf-run"));
    }

    public String source() {
        return require("orders.source");
    }

    public int quantity() {
        return intValue("orders.quantity", 1);
    }

    public double priceOffsetPercent() {
        return doubleValue("orders.priceOffsetPercent", 30);
    }

    public double tickSize() {
        return doubleValue("orders.tickSize", 0.01);
    }

    public String cashCaller() {
        return optional("orders.cashCaller").orElse("titres-trading-performance-tests");
    }

    /** Time between two orders of the same client in the closed model. */
    public Duration pace() {
        return Duration.ofSeconds(optional("perf.paceSeconds").map(Integer::parseInt)
                .orElse(intValue("orders.paceSeconds", 5)));
    }

    public Duration pollInterval() {
        return Duration.ofMillis(intValue("poll.intervalMs", 500));
    }

    public Duration pollTimeout() {
        return Duration.ofMillis(intValue("poll.timeoutMs", 20000));
    }

    /** {@code -Dperf.maxOrders} raises the profile's cap for a capacity run, explicitly. */
    public int maxOrders() {
        return optional("perf.maxOrders").map(Integer::parseInt)
                .orElse(intValue("limits.maxOrdersPerCampaign", 500));
    }

    public Path accountsFile() {
        return projectDir.resolve(require("data.accounts"));
    }

    public Path instrumentsFile() {
        return projectDir.resolve(require("data.instruments"));
    }

    /** Parameters worth recording with a run; secrets excluded. */
    public Map<String, String> publicParameters() {
        Map<String, String> map = new HashMap<>();
        values.forEach((k, v) -> {
            if (!k.startsWith("secret.")) {
                map.put(k, v);
            }
        });
        return map;
    }

    @Override
    public String toString() {
        return "PerfConfig[env=" + env() + ", baseUrl=" + values.get("selfcare.baseUrl") + ", campaign=" + values.get("perf.campaignId") + "]";
    }
}
