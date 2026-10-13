package com.attijariwafa.titres.perf.actions;

import com.attijariwafa.titres.perf.support.Thresholds;
import io.gatling.javaapi.core.ChainBuilder;

import static io.gatling.javaapi.core.CoreDsl.StringBody;
import static io.gatling.javaapi.core.CoreDsl.doIf;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

/**
 * {@code POST /xcastrade/cancel} for the order of the current iteration. From SUBMITTED on the
 * API sends ORDERCANCEL to the broker and answers once the broker took the request; the order
 * only changes state with the ORDER_CANCELLED callback, so nothing is polled afterwards.
 */
public final class CancelOrder {

    private CancelOrder() {
    }

    public static ChainBuilder chain() {
        return doIf(session -> session.contains("mainReference") && !session.getString("mainReference").isEmpty()).then(
                exec(http(Thresholds.CANCEL)
                        .post("/xcastrade/cancel")
                        .body(StringBody(session -> "{"
                                + "\"mainReference\":\"" + session.getString("mainReference") + "\","
                                + "\"clientSecAccount\":\"" + session.getString("secaccount") + "\""
                                + "}")).asJson()
                        .check(status().is(200))
                        .check(jsonPath("$.returnCode").ofInt().in(0, 200))));
    }
}
