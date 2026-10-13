package com.attijariwafa.titres.perf.support;

import com.attijariwafa.titres.perf.config.PerfConfig;
import io.gatling.javaapi.core.ChainBuilder;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import static io.gatling.javaapi.core.CoreDsl.exitHereIf;

/**
 * Two ways a run stops booking before its injection profile ends: the harness drops an
 * {@code ABORT} file in the run directory (5xx share above the limit, operator decision), or
 * the campaign reached its order cap. Both are checked at the top of every user loop.
 */
public final class AbortGuard {

    private static final AtomicInteger ORDERS_BOOKED = new AtomicInteger();
    private static final AtomicLong LAST_FILE_CHECK = new AtomicLong();
    private static volatile boolean abortFileSeen;

    private AbortGuard() {
    }

    public static Path abortFile() {
        return PerfConfig.get().runDir().resolve("ABORT");
    }

    /** True once the ABORT file exists; the file system is consulted at most once a second. */
    public static boolean abortRequested() {
        if (abortFileSeen) {
            return true;
        }
        long now = System.currentTimeMillis();
        long last = LAST_FILE_CHECK.get();
        if (now - last > 1000 && LAST_FILE_CHECK.compareAndSet(last, now)) {
            if (Files.exists(abortFile())) {
                abortFileSeen = true;
                System.err.println("[perf] ABORT file found, users exit at their next iteration");
            }
        }
        return abortFileSeen;
    }

    /** Counts one booking attempt; false when the campaign cap is reached. */
    public static boolean allowOrder() {
        return ORDERS_BOOKED.incrementAndGet() <= PerfConfig.get().maxOrders();
    }

    public static boolean capReached() {
        return ORDERS_BOOKED.get() >= PerfConfig.get().maxOrders();
    }

    public static int ordersBooked() {
        return Math.min(ORDERS_BOOKED.get(), PerfConfig.get().maxOrders());
    }

    /** To put first in a loop that books orders. */
    public static ChainBuilder exitWhenAbortedOrCapped() {
        return exitHereIf(session -> abortRequested() || capReached());
    }

    /** To put first in a read-only loop. */
    public static ChainBuilder exitWhenAborted() {
        return exitHereIf(session -> abortRequested());
    }
}
