package com.attijariwafa.titres.perf.scenarios;

import com.attijariwafa.titres.perf.actions.PortfolioReads;
import com.attijariwafa.titres.perf.data.AccountPool;
import com.attijariwafa.titres.perf.support.AbortGuard;
import io.gatling.javaapi.core.ScenarioBuilder;

import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.listFeeder;
import static io.gatling.javaapi.core.CoreDsl.percent;
import static io.gatling.javaapi.core.CoreDsl.randomSwitch;
import static io.gatling.javaapi.core.CoreDsl.scenario;

/**
 * The request mix of the mobile application: mostly reads, a few cash balance checks, one
 * order in ten arrivals. Weights are placeholders until the business provides production
 * statistics (phase 3).
 */
public final class MobileMixScenario {

    private MobileMixScenario() {
    }

    public static ScenarioBuilder arrivals() {
        return scenario("mobile-mix")
                .feed(listFeeder(AccountPool.feederRows()).circular())
                .exec(AbortGuard.exitWhenAborted())
                .randomSwitch().on(
                        percent(40.0).then(PortfolioReads.listValuedHot()),
                        percent(20.0).then(PortfolioReads.listOrders()),
                        percent(15.0).then(PortfolioReads.tradableAssets()),
                        percent(10.0).then(PortfolioReads.secAccounts()),
                        percent(5.0).then(PortfolioReads.cashBalances()),
                        percent(10.0).then(exec(AbortGuard.exitWhenAbortedOrCapped()).exec(OrderFlowScenario.oneOrder())));
    }
}
