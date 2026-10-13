package com.attijariwafa.titres.perf.scenarios;

import com.attijariwafa.titres.perf.actions.Book;
import com.attijariwafa.titres.perf.actions.CancelOrder;
import com.attijariwafa.titres.perf.actions.PollUntilSubmitted;
import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.AccountPool;
import com.attijariwafa.titres.perf.support.AbortGuard;
import com.attijariwafa.titres.perf.support.CampaignContext;
import io.gatling.javaapi.core.ChainBuilder;
import io.gatling.javaapi.core.ScenarioBuilder;

import java.time.Duration;

import static io.gatling.javaapi.core.CoreDsl.doIf;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.feed;
import static io.gatling.javaapi.core.CoreDsl.forever;
import static io.gatling.javaapi.core.CoreDsl.listFeeder;
import static io.gatling.javaapi.core.CoreDsl.pace;
import static io.gatling.javaapi.core.CoreDsl.repeat;
import static io.gatling.javaapi.core.CoreDsl.scenario;

/**
 * A client placing orders: book, watch the order reach the market, optionally cancel it.
 * One virtual user owns one account for its whole life (closed model), or one order is one
 * user (open model, capacity ramp).
 */
public final class OrderFlowScenario {

    private OrderFlowScenario() {
    }

    /** One order end to end, on the account already in the session. */
    public static ChainBuilder oneOrder() {
        ChainBuilder flow = exec(Book.configuredSide()).exec(PollUntilSubmitted.chain());
        if (PerfConfig.get().cancelAfterSubmission()) {
            flow = flow.exec(doIf(session -> session.getBoolean("terminal") && "105".equals(session.getString("orderStatus")))
                    .then(CancelOrder.chain()));
        }
        return flow;
    }

    /** Closed model: the user keeps its account and books every {@code paceSeconds}. */
    public static ScenarioBuilder steady(Duration paceBetweenOrders) {
        return scenario("order-flow")
                .feed(listFeeder(AccountPool.feederRows()).circular())
                .exec(session -> session.set("userIndex", CampaignContext.nextUserIndex()))
                .forever().on(
                        AbortGuard.exitWhenAbortedOrCapped()
                                .pace(paceBetweenOrders)
                                .exec(oneOrder()));
    }

    /** Closed model, a fixed number of orders per user (smoke). */
    public static ScenarioBuilder fixed(int ordersPerUser, Duration paceBetweenOrders) {
        return scenario("order-flow")
                .feed(listFeeder(AccountPool.feederRows()).circular())
                .exec(session -> session.set("userIndex", CampaignContext.nextUserIndex()))
                .repeat(ordersPerUser).on(
                        AbortGuard.exitWhenAbortedOrCapped()
                                .pace(paceBetweenOrders)
                                .exec(oneOrder()));
    }

    /** Open model: every arrival is one order on the next account of the pool. */
    public static ScenarioBuilder oneShot() {
        return scenario("order-flow-arrivals")
                .feed(listFeeder(AccountPool.feederRows()).circular())
                .exec(AbortGuard.exitWhenAbortedOrCapped())
                .exec(oneOrder());
    }
}
