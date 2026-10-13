package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.scenarios.OrderFlowScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import com.attijariwafa.titres.perf.support.Workloads;
import io.gatling.javaapi.core.OpenInjectionStep;
import io.gatling.javaapi.core.Simulation;

import java.time.Duration;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;

/**
 * Finds the limit: order arrivals grow by {@code -Dperf.targetRate} orders per second
 * (0.5/s by default) at every level, each level held two minutes, eight levels. The harness
 * derives the knee from the per-level latency and the RECEIVED backlog. Pass
 * {@code -Dperf.maxOrders} explicitly: the default campaign cap of 500 stops the ramp early.
 */
public class CapacityRampSimulation extends Simulation {

    {
        InstrumentCatalog.load();
        CampaignContext.start("CapacityRamp");
        PerfConfig config = PerfConfig.get();
        double step = config.targetRate().orElse(0.5);
        int levels = config.intValue("perf.levels", 8);
        setUp(OrderFlowScenario.oneShot()
                .injectOpen(Workloads.capacityRamp(step, step, levels, Duration.ofMinutes(2)).toArray(new OpenInjectionStep[0])))
                .protocols(selfcare())
                .assertions(Thresholds.capacity());
    }

    @Override
    public void after() {
        OrderLedger.close();
        CampaignContext.end();
    }
}
