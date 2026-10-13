package com.attijariwafa.titres.perf.simulations;

import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.scenarios.MobileMixScenario;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.OrderLedger;
import com.attijariwafa.titres.perf.support.Thresholds;
import com.attijariwafa.titres.perf.support.Workloads;
import io.gatling.javaapi.core.OpenInjectionStep;
import io.gatling.javaapi.core.Simulation;

import static com.attijariwafa.titres.perf.protocol.SelfcareProtocol.selfcare;

/**
 * The mobile request mix at {@code -Dperf.profile=nominal|peak} (or an explicit
 * {@code -Dperf.targetRate}), ramped then held for {@code -Dperf.duration}.
 */
public class MobileMixSimulation extends Simulation {

    {
        InstrumentCatalog.load();
        CampaignContext.start("MobileMix");
        setUp(MobileMixScenario.arrivals()
                .injectOpen(Workloads.rampThenHold(Workloads.profileRate()).toArray(new OpenInjectionStep[0])))
                .protocols(selfcare())
                .assertions(Thresholds.mobileMix());
    }

    @Override
    public void after() {
        OrderLedger.close();
        CampaignContext.end();
    }
}
