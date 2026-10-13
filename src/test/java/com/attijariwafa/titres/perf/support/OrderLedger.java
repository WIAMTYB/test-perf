package com.attijariwafa.titres.perf.support;

import com.attijariwafa.titres.perf.config.PerfConfig;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;

/**
 * One line per order the campaign booked, written as the virtual user observes it:
 * the cross-check between the Gatling report and what ORDERS holds. Flushed in
 * {@code after()} of the simulation.
 */
public final class OrderLedger {

    public static final String HEADER = "clientReference,bankOrderId,secAccount,cashAccount,isin,side,price,quantity,"
            + "bookHttpStatus,bookReturnCode,bookedAt,submittedAt,timeToSubmittedMs,polls,finalStatus,failReason";

    private static final Object LOCK = new Object();
    private static BufferedWriter writer;

    private OrderLedger() {
    }

    public static Path file() {
        return PerfConfig.get().runDir().resolve("orders-ledger.csv");
    }

    public static void append(String clientReference, String bankOrderId, String secAccount, String cashAccount,
                              String isin, String side, String price, int quantity, int bookHttpStatus,
                              String bookReturnCode, long bookedAtMs, long submittedAtMs, int polls,
                              String finalStatus, String failReason) {
        String line = String.join(",",
                clientReference, nullToEmpty(bankOrderId), secAccount, cashAccount, isin, side, nullToEmpty(price),
                Integer.toString(quantity), Integer.toString(bookHttpStatus), nullToEmpty(bookReturnCode),
                Instant.ofEpochMilli(bookedAtMs).toString(),
                submittedAtMs > 0 ? Instant.ofEpochMilli(submittedAtMs).toString() : "",
                submittedAtMs > 0 ? Long.toString(submittedAtMs - bookedAtMs) : "",
                Integer.toString(polls), nullToEmpty(finalStatus), csv(failReason));
        synchronized (LOCK) {
            try {
                if (writer == null) {
                    Path file = file();
                    Files.createDirectories(file.getParent());
                    boolean fresh = !Files.exists(file) || Files.size(file) == 0;
                    writer = Files.newBufferedWriter(file, StandardCharsets.UTF_8,
                            StandardOpenOption.CREATE, StandardOpenOption.APPEND);
                    if (fresh) {
                        writer.write(HEADER);
                        writer.newLine();
                    }
                }
                writer.write(line);
                writer.newLine();
            } catch (IOException e) {
                System.err.println("[perf] ledger write failed: " + e.getMessage());
            }
        }
    }

    public static void close() {
        synchronized (LOCK) {
            if (writer != null) {
                try {
                    writer.flush();
                    writer.close();
                } catch (IOException e) {
                    System.err.println("[perf] ledger close failed: " + e.getMessage());
                }
                writer = null;
            }
        }
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private static String csv(String value) {
        if (value == null) {
            return "";
        }
        String cleaned = value.replace('\n', ' ').replace('\r', ' ');
        return cleaned.contains(",") || cleaned.contains("\"")
                ? "\"" + cleaned.replace("\"", "\"\"") + "\""
                : cleaned;
    }
}
