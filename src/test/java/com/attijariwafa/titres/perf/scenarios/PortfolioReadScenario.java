package com.attijariwafa.titres.perf.scenarios;

import com.attijariwafa.titres.perf.actions.PortfolioReads;
import com.attijariwafa.titres.perf.data.AccountPool;
import com.attijariwafa.titres.perf.support.AbortGuard;
import io.gatling.javaapi.core.ScenarioBuilder;

import static io.gatling.javaapi.core.CoreDsl.listFeeder;
import static io.gatling.javaapi.core.CoreDsl.percent;
import static io.gatling.javaapi.core.CoreDsl.randomSwitch;
import static io.gatling.javaapi.core.CoreDsl.scenario;

/**
 * A client looking at its portfolio: valued positions (70 % on its own account, a cache
 * hit; 30 % on another combination, a miss), its orders and its accounts. Open model: each
 * arrival is one screen refresh.
 */
public final class PortfolioReadScenario {

    private PortfolioReadScenario() {
    }

    public static ScenarioBuilder arrivals() {
        return scenario("portfolio-read")
                .feed(listFeeder(AccountPool.feederRows()).circular())
                .exec(AbortGuard.exitWhenAborted())
                .randomSwitch().on(
                        percent(45.0).then(PortfolioReads.listValuedHot()),
                        percent(20.0).then(PortfolioReads.listValuedCold()),
                        percent(25.0).then(PortfolioReads.listOrders()),
                        percent(10.0).then(PortfolioReads.secAccounts()));
    }
}
