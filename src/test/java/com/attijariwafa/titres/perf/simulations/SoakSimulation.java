package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.scenarios.MobileMixScenario;
import com.attijariwafa.titres.perf.scenarios.OrderFlowScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import com.attijariwafa.titres.perf.support.Workloads;
import io.gatling.javaapi.core.OpenInjectionStep;
import io.gatling.javaapi.core.Simulation;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;

/**
 * Nominal mobile mix held for a long {@code -Dperf.duration} (two hours is the reference),
 * with a steady trickle of one order a minute on top. Judged by the harness on the p95 drift
 * between the first and last quarter hour, Hikari pending connections and pod memory growth.
 */
public class SoakSimulation extends Simulation {

    {
        InstrumentCatalog.load();
        CampaignContext.start("Soak");
        setUp(
                MobileMixScenario.arrivals()
                        .injectOpen(Workloads.rampThenHold(Workloads.NOMINAL_RATE).toArray(new OpenInjectionStep[0])),
                OrderFlowScenario.oneShot()
                        .injectOpen(Workloads.trickle(1.0, Workloads.duration()).toArray(new OpenInjectionStep[0])))
                .protocols(selfcare())
                .assertions(Thresholds.longRun());
    }

    @Override
    public void after() {
        OrderLedger.close();
        CampaignContext.end();
    }
}
