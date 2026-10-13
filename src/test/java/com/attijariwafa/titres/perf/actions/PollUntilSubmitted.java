package com.attijariwafa.titres.perf.actions;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import io.gatling.javaapi.core.ChainBuilder;
import io.gatling.javaapi.core.Session;

import java.util.Set;

import static io.gatling.javaapi.core.CoreDsl.asLongAs;
import static io.gatling.javaapi.core.CoreDsl.doIf;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.group;
import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.core.CoreDsl.pause;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

/**
 * Polls {@code GET /xcastrade/v2/listorders} for the order just booked until the client-visible
 * status leaves 104 (before the broker): 105 means SUBMITTED. The whole loop runs inside the
 * {@code time-to-submitted} group, whose duration is the client-observed latency the report
 * and the assertions use; the exact figure also goes to the ledger.
 *
 * <p>The list endpoint returns Oracle column labels as JSON keys; both cases are read.
 */
public final class PollUntilSubmitted {

    /** Statuses after which polling stops: at market, filled, partial, rejected, expired, cancelled. */
    static final Set<String> TERMINAL = Set.of("105", "106", "107", "102", "103", "108", "109");
    static final Set<String> FAILED = Set.of("102");

    private PollUntilSubmitted() {
    }

    public static ChainBuilder chain() {
        PerfConfig config = PerfConfig.get();
        long timeoutMs = config.pollTimeout().toMillis();
        return doIf(session -> session.getBoolean("orderAllowed") && session.getInt("bookStatus") == 200
                && !session.getString("mainReference").isEmpty()).then(
                exec(session -> session
                        .set("pollStart", System.currentTimeMillis())
                        .set("polls", 0)
                        .set("orderStatus", "")
                        .set("failReason", "")
                        .set("submittedAt", 0L)
                        .set("terminal", false))
                .group(Thresholds.TIME_TO_SUBMITTED).on(
                        asLongAs(session -> !session.getBoolean("terminal")
                                && System.currentTimeMillis() - session.getLong("pollStart") < timeoutMs).on(
                                exec(http(Thresholds.POLL)
                                        .get("/xcastrade/v2/listorders")
                                        .queryParam("secaccount", "#{secaccount}")
                                        .queryParam("skip", "0")
                                        .queryParam("take", "20")
                                        .queryParam("filter[0][field]", "referenceclient")
                                        .queryParam("filter[0][operator]", "eq")
                                        .queryParam("filter[0][value]", "#{clientReference}")
                                        .check(status().in(200, 204))
                                        .check(jsonPath("$.data[0].STATUS").optional().saveAs("statusUpper"))
                                        .check(jsonPath("$.data[0].status").optional().saveAs("statusLower"))
                                        .check(jsonPath("$.data[0].FAILREASON").optional().saveAs("failUpper"))
                                        .check(jsonPath("$.data[0].failreason").optional().saveAs("failLower")))
                                .exec(PollUntilSubmitted::observe)
                                .doIf(session -> !session.getBoolean("terminal")).then(pause(config.pollInterval()))))
                .exec(PollUntilSubmitted::record));
    }

    private static Session observe(Session session) {
        String status = first(session, "statusUpper", "statusLower");
        String fail = first(session, "failUpper", "failLower");
        int polls = session.getInt("polls") + 1;
        Session next = session.set("polls", polls).set("orderStatus", status).set("failReason", fail)
                .remove("statusUpper").remove("statusLower").remove("failUpper").remove("failLower");
        if (TERMINAL.contains(status)) {
            return next.set("terminal", true).set("submittedAt", System.currentTimeMillis());
        }
        return next;
    }

    private static Session record(Session session) {
        String status = session.getString("orderStatus");
        boolean submitted = session.getBoolean("terminal") && !FAILED.contains(status);
        OrderLedger.append(
                session.getString("clientReference"), session.getString("mainReference"),
                session.getString("secaccount"), session.getString("cashaccount"), session.getString("isin"),
                session.getString("side"), session.getString("price"), session.getInt("quantity"),
                session.getInt("bookStatus"), session.getString("bookReturnCode"), session.getLong("bookedAt"),
                submitted ? session.getLong("submittedAt") : 0L, session.getInt("polls"),
                session.getBoolean("terminal") ? status : "TIMEOUT", session.getString("failReason"));
        if (!submitted) {
            return session.markAsFailed();
        }
        return session;
    }

    private static String first(Session session, String... keys) {
        for (String key : keys) {
            if (session.contains(key)) {
                Object value = session.get(key);
                if (value != null && !value.toString().isBlank()) {
                    return value.toString();
                }
            }
        }
        return "";
    }
}
