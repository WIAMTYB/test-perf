package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.scenarios.OrderFlowScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import io.gatling.javaapi.core.Simulation;

import java.time.Duration;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;
import static io.gatling.javaapi.core.CoreDsl.atOnceUsers;

/**
 * Two clients, ten orders each, two seconds apart: proves the chain end to end in about a
 * minute and leaves twenty attributable orders in ORDERS. The first thing to run on a new
 * environment or after a change of the platform.
 */
public class SmokeSimulation extends Simulation {

    {
        InstrumentCatalog.load();
        CampaignContext.start("Smoke");
        setUp(OrderFlowScenario.fixed(10, Duration.ofSeconds(2)).injectOpen(atOnceUsers(2)))
                .protocols(selfcare())
                .assertions(Thresholds.smoke());
    }

    @Override
    public void after() {
        OrderLedger.close();
        CampaignContext.end();
    }
}
