package com.attijariwafa.titres.perf.data;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.support.InsecureTls;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * The instruments a campaign trades, from {@code data/<env>/instruments.csv}, with the
 * reference price of each read once from {@code /tradableasset/v2/listforxcastrade} (the
 * Megara end-of-day price the validation step uses for the 35 % band). An instrument the API
 * does not price is dropped: the order would pass validation and be refused by the broker.
 */
public final class InstrumentCatalog {

    public record Instrument(String isin, String symbol, BigDecimal tickSize, BigDecimal referencePrice) {
    }

    private static final Map<String, Instrument> PRICED = new ConcurrentHashMap<>();
    private static volatile List<Instrument> ordered = List.of();

    private InstrumentCatalog() {
    }

    /** Loads the catalog; called from a simulation's {@code before()} hook, idempotent. */
    public static synchronized List<Instrument> load() {
        if (!ordered.isEmpty()) {
            return ordered;
        }
        PerfConfig config = PerfConfig.get();
        List<String[]> wanted = readCsv(config.instrumentsFile());
        Map<String, BigDecimal> prices = fetchPrices(config);
        List<Instrument> instruments = new ArrayList<>();
        for (String[] row : wanted) {
            String isin = row[0];
            BigDecimal price = prices.get(isin);
            if (price == null || price.signum() <= 0) {
                System.err.println("[perf] instrument " + isin + " has no reference price on " + config.env() + ": skipped");
                continue;
            }
            Instrument instrument = new Instrument(isin, row[1], new BigDecimal(row[2]), price);
            PRICED.put(isin, instrument);
            instruments.add(instrument);
        }
        if (instruments.isEmpty()) {
            throw new IllegalStateException("No priced instrument available: check " + config.instrumentsFile());
        }
        ordered = List.copyOf(instruments);
        System.out.println("[perf] instruments: " + ordered);
        return ordered;
    }

    public static List<Instrument> instruments() {
        if (ordered.isEmpty()) {
            load();
        }
        return ordered;
    }

    public static Instrument byIsin(String isin) {
        Instrument instrument = PRICED.get(isin);
        if (instrument == null) {
            throw new IllegalStateException("Instrument " + isin + " is not in the priced catalog");
        }
        return instrument;
    }

    /** Rows of (isin, symbol, tickSize) for the enabled instruments. */
    static List<String[]> readCsv(Path file) {
        if (!Files.exists(file)) {
            throw new IllegalStateException("Instrument file not found: " + file);
        }
        try {
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            List<String> header = Arrays.asList(lines.get(0).strip().split(","));
            int isin = header.indexOf("isin");
            int symbol = header.indexOf("symbol");
            int tick = header.indexOf("tickSize");
            int enabled = header.indexOf("enabled");
            List<String[]> rows = new ArrayList<>();
            for (String line : lines.subList(1, lines.size())) {
                if (line.isBlank()) {
                    continue;
                }
                String[] cells = line.split(",", -1);
                if (enabled >= 0 && !"true".equalsIgnoreCase(cells[enabled].strip())) {
                    continue;
                }
                rows.add(new String[]{cells[isin].strip(), symbol >= 0 ? cells[symbol].strip() : "",
                        tick >= 0 && !cells[tick].isBlank() ? cells[tick].strip() : "0.01"});
            }
            return rows;
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read " + file, e);
        }
    }

    /** One GET on the client API; the response is a JSON array of XcasAssetResponse. */
    static Map<String, BigDecimal> fetchPrices(PerfConfig config) {
        HttpClient client = HttpClient.newBuilder()
                .sslContext(InsecureTls.context())
                .connectTimeout(Duration.ofSeconds(10))
                .build();
        HttpRequest request = HttpRequest.newBuilder(URI.create(config.baseUrl() + "/tradableasset/v2/listforxcastrade"))
                .header("X-Api-Key", config.apiKey())
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(60))
                .GET()
                .build();
        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() != 200) {
                throw new IllegalStateException("listforxcastrade answered HTTP " + response.statusCode() + " on " + config.env());
            }
            return parsePrices(response.body());
        } catch (IOException e) {
            throw new IllegalStateException("Cannot reach " + config.baseUrl(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while loading the instruments", e);
        }
    }

    /** isin -> price for every active, priced asset of the array (Jackson ships with Gatling). */
    static Map<String, BigDecimal> parsePrices(String body) {
        Map<String, BigDecimal> prices = new ConcurrentHashMap<>();
        try {
            JsonNode root = new ObjectMapper().readTree(body);
            for (JsonNode asset : root) {
                JsonNode isin = asset.get("isin");
                JsonNode price = asset.get("price");
                JsonNode active = asset.get("active");
                if (isin == null || price == null || price.isNull()) {
                    continue;
                }
                if (active != null && !active.isNull() && !active.asBoolean()) {
                    continue;
                }
                prices.put(isin.asText(), price.isNumber() ? price.decimalValue() : new BigDecimal(price.asText()));
            }
        } catch (IOException e) {
            throw new IllegalStateException("listforxcastrade did not answer a JSON array", e);
        }
        return prices;
    }
}
