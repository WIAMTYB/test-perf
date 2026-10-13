package com.attijariwafa.titres.perf.support;

import io.gatling.javaapi.core.Assertion;

import java.util.List;

import static io.gatling.javaapi.core.CoreDsl.details;
import static io.gatling.javaapi.core.CoreDsl.global;

/**
 * Pass/fail thresholds of each simulation, in one place so the business can revise them
 * (phase 3) without touching the scenarios. Initial values are placeholders that reflect
 * what recette does today with the chased saga (time to SUBMITTED about one second).
 */
public final class Thresholds {

    public static final String BOOK = "book";
    public static final String BOOK_CONFLICT = "book-conflict";
    public static final String TIME_TO_SUBMITTED = "time-to-submitted";
    public static final String POLL = "poll-order";
    public static final String CANCEL = "cancel";
    public static final String LIST_VALUED_HOT = "listvalued-hot";
    public static final String LIST_VALUED_COLD = "listvalued-cold";
    public static final String LIST_ORDERS = "listorders";
    public static final String SEC_ACCOUNTS = "secaccounts";
    public static final String TRADABLE_ASSETS = "tradableassets";
    public static final String CASH_BALANCES = "cash-balances";

    private Thresholds() {
    }

    public static List<Assertion> smoke() {
        return List.of(
                details(BOOK).failedRequests().count().is(0L),
                details(TIME_TO_SUBMITTED).responseTime().max().lt(10_000),
                global().failedRequests().percent().lt(1.0));
    }

    public static List<Assertion> orderFlow() {
        return List.of(
                details(BOOK).responseTime().percentile(95).lt(500),
                details(BOOK).responseTime().percentile(99).lt(1_000),
                details(TIME_TO_SUBMITTED).responseTime().percentile(95).lt(3_000),
                details(TIME_TO_SUBMITTED).responseTime().percentile(99).lt(5_000),
                global().failedRequests().percent().lt(1.0));
    }

    public static List<Assertion> portfolioRead() {
        return List.of(
                details(LIST_VALUED_HOT).responseTime().percentile(95).lt(1_000),
                details(LIST_VALUED_COLD).responseTime().percentile(95).lt(5_000),
                details(LIST_ORDERS).responseTime().percentile(95).lt(1_000),
                global().failedRequests().percent().lt(1.0));
    }

    public static List<Assertion> mobileMix() {
        return List.of(
                details(LIST_VALUED_HOT).responseTime().percentile(95).lt(1_000),
                details(LIST_ORDERS).responseTime().percentile(95).lt(1_000),
                details(TRADABLE_ASSETS).responseTime().percentile(95).lt(1_500),
                details(SEC_ACCOUNTS).responseTime().percentile(95).lt(1_000),
                details(BOOK).responseTime().percentile(95).lt(500),
                global().failedRequests().percent().lt(1.0));
    }

    /** Soak and spike are judged on the drift and the recovery the dossier computes. */
    public static List<Assertion> longRun() {
        return List.of(global().failedRequests().percent().lt(2.0));
    }

    /** A capacity ramp is exploratory: it never fails on latency, only on a broken run. */
    public static List<Assertion> capacity() {
        return List.of(global().successfulRequests().count().gt(0L));
    }
}
