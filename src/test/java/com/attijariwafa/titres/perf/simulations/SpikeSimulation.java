package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.scenarios.MobileMixScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import com.attijariwafa.titres.perf.support.Workloads;
import io.gatling.javaapi.core.OpenInjectionStep;
import io.gatling.javaapi.core.Simulation;

import java.time.Duration;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;

/**
 * Nominal for three minutes, ten times nominal for two minutes, nominal for five minutes.
 * The harness reports how long the p95 takes to come back under its nominal level once the
 * burst ends.
 */
public class SpikeSimulation extends Simulation {

    {
        InstrumentCatalog.load();
        CampaignContext.start("Spike");
        double nominal = Workloads.NOMINAL_RATE;
        setUp(MobileMixScenario.arrivals()
                .injectOpen(Workloads.spike(nominal, 10.0, Duration.ofMinutes(3), Duration.ofMinutes(2), Duration.ofMinutes(5))
                        .toArray(new OpenInjectionStep[0])))
                .protocols(selfcare())
                .assertions(Thresholds.longRun());
    }

    @Override
    public void after() {
        OrderLedger.close();
        CampaignContext.end();
    }
}
