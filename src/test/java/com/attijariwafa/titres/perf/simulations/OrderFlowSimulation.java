package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.scenarios.OrderFlowScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import com.attijariwafa.titres.perf.support.Workloads;
import io.gatling.javaapi.core.ClosedInjectionStep;
import io.gatling.javaapi.core.Simulation;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;

/**
 * Closed model: one client per pool account, each booking an order every
 * {@code orders.paceSeconds} for {@code -Dperf.duration}; {@code -Dperf.side=SELL} for sells,
 * {@code -Dperf.cancel=true} to cancel each order once at the market.
 */
public class OrderFlowSimulation extends Simulation {

    {
        InstrumentCatalog.load();
        CampaignContext.start("OrderFlow");
        setUp(OrderFlowScenario.steady(PerfConfig.get().pace())
                .injectClosed(Workloads.oneUserPerAccount().toArray(new ClosedInjectionStep[0])))
                .protocols(selfcare())
                .assertions(Thresholds.orderFlow());
    }

    @Override
    public void after() {
        OrderLedger.close();
        CampaignContext.end();
    }
}
