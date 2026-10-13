package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.scenarios.PortfolioReadScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.Thresholds;
import com.attijariwafa.titres.perf.support.Workloads;
import io.gatling.javaapi.core.OpenInjectionStep;
import io.gatling.javaapi.core.Simulation;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;

/**
 * Open model of portfolio screens: ramp to {@code -Dperf.targetRate} refreshes per second
 * (10/s by default) then hold for {@code -Dperf.duration}. No order is booked.
 */
public class PortfolioReadSimulation extends Simulation {

    {
        CampaignContext.start("PortfolioRead");
        setUp(PortfolioReadScenario.arrivals()
                .injectOpen(Workloads.rampThenHold(10.0).toArray(new OpenInjectionStep[0])))
                .protocols(selfcare())
                .assertions(Thresholds.portfolioRead());
    }

    @Override
    public void after() {
        CampaignContext.end();
    }
}
