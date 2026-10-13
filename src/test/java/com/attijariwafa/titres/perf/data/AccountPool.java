package com.attijariwafa.titres.perf.data;

import com.attijariwafa.titres.perf.config.PerfConfig;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The client accounts a campaign may trade on, from {@code data/<env>/accounts.csv}.
 * One virtual user owns one account: the API serialises bookings per account and ISIN
 * with a lock (HTTP 409 when busy), so two users on one account would only measure that lock.
 */
public final class AccountPool {

    public record Account(String secAccount, String cashAccount, String label, List<String> sellIsins) {
    }

    private static final List<Account> ACCOUNTS = read(PerfConfig.get().accountsFile());

    private AccountPool() {
    }

    public static List<Account> accounts() {
        return ACCOUNTS;
    }

    public static int size() {
        return ACCOUNTS.size();
    }

    /** Rows for a Gatling feeder: one map per account, keys usable as {@code #{secaccount}}. */
    public static List<Map<String, Object>> feederRows() {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Account account : ACCOUNTS) {
            Map<String, Object> row = new HashMap<>();
            row.put("secaccount", account.secAccount());
            row.put("cashaccount", account.cashAccount());
            row.put("accountLabel", account.label());
            row.put("sellIsins", String.join("|", account.sellIsins()));
            rows.add(row);
        }
        return rows;
    }

    static List<Account> read(Path file) {
        if (!Files.exists(file)) {
            throw new IllegalStateException("Account pool file not found: " + file);
        }
        List<Account> accounts = new ArrayList<>();
        try {
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            if (lines.isEmpty()) {
                throw new IllegalStateException("Account pool file is empty: " + file);
            }
            List<String> header = Arrays.asList(lines.get(0).strip().split(","));
            int sec = header.indexOf("secaccount");
            int cash = header.indexOf("cashaccount");
            int label = header.indexOf("label");
            int sell = header.indexOf("sellIsins");
            int enabled = header.indexOf("enabled");
            for (String line : lines.subList(1, lines.size())) {
                if (line.isBlank()) {
                    continue;
                }
                String[] cells = line.split(",", -1);
                if (enabled >= 0 && !"true".equalsIgnoreCase(cells[enabled].strip())) {
                    continue;
                }
                List<String> isins = sell >= 0 && !cells[sell].isBlank()
                        ? Arrays.stream(cells[sell].split("\\|")).map(String::strip).toList()
                        : List.of();
                accounts.add(new Account(cells[sec].strip(), cells[cash].strip(),
                        label >= 0 ? cells[label].strip() : "", isins));
            }
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read " + file, e);
        }
        if (accounts.isEmpty()) {
            throw new IllegalStateException("No enabled account in " + file);
        }
        return List.copyOf(accounts);
    }
}
