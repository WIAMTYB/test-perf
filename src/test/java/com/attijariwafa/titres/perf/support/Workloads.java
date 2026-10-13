package com.attijariwafa.titres.perf.support;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.AccountPool;
import io.gatling.javaapi.core.ClosedInjectionStep;
import io.gatling.javaapi.core.OpenInjectionStep;

import java.time.Duration;
import java.util.List;

import static io.gatling.javaapi.core.CoreDsl.constantConcurrentUsers;
import static io.gatling.javaapi.core.CoreDsl.constantUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.incrementUsersPerSec;
import static io.gatling.javaapi.core.CoreDsl.nothingFor;
import static io.gatling.javaapi.core.CoreDsl.rampUsersPerSec;

/**
 * Injection profiles built from the campaign parameters, so the same simulation class
 * serves a 2-minute smoke and a 2-hour soak with different {@code -Dperf.*} values.
 */
public final class Workloads {

    /** Request rates of the mobile mix, per second, until the business gives real figures. */
    public static final double NOMINAL_RATE = 5.0;
    public static final double PEAK_RATE = 25.0;

    private Workloads() {
    }

    public static Duration duration() {
        return PerfConfig.get().duration();
    }

    /** Closed model: one user per account unless {@code -Dperf.users} is lower. */
    public static List<ClosedInjectionStep> oneUserPerAccount() {
        int users = PerfConfig.get().users().map(u -> Math.min(u, AccountPool.size())).orElse(AccountPool.size());
        return List.of(constantConcurrentUsers(users).during(duration()));
    }

    /** Open model: ramp to the target rate over two minutes (or less), then hold. */
    public static List<OpenInjectionStep> rampThenHold(double fallbackRate) {
        double rate = PerfConfig.get().targetRate().orElse(fallbackRate);
        Duration total = duration();
        Duration ramp = total.compareTo(Duration.ofMinutes(4)) > 0 ? Duration.ofMinutes(2) : total.dividedBy(4);
        return List.of(
                rampUsersPerSec(Math.max(0.1, rate / 10)).to(rate).during(ramp),
                constantUsersPerSec(rate).during(total.minus(ramp)));
    }

    public static double profileRate() {
        return "peak".equals(PerfConfig.get().profile()) ? PEAK_RATE : NOMINAL_RATE;
    }

    /** Capacity ramp: levels of {@code step} users/s, each held two minutes. */
    public static List<OpenInjectionStep> capacityRamp(double base, double step, int levels, Duration level) {
        return List.of(incrementUsersPerSec(step)
                .times(levels)
                .eachLevelLasting(level)
                .separatedByRampsLasting(Duration.ofSeconds(30))
                .startingFrom(base));
    }

    /** Spike: nominal, a burst at {@code factor} times nominal, back to nominal. */
    public static List<OpenInjectionStep> spike(double nominal, double factor, Duration before, Duration burst, Duration after) {
        return List.of(
                constantUsersPerSec(nominal).during(before),
                rampUsersPerSec(nominal).to(nominal * factor).during(Duration.ofSeconds(10)),
                constantUsersPerSec(nominal * factor).during(burst),
                rampUsersPerSec(nominal * factor).to(nominal).during(Duration.ofSeconds(10)),
                constantUsersPerSec(nominal).during(after));
    }

    /** A trickle of orders during a long read-heavy run. */
    public static List<OpenInjectionStep> trickle(double perMinute, Duration total) {
        return List.of(nothingFor(Duration.ofSeconds(5)), constantUsersPerSec(perMinute / 60.0).during(total));
    }
}
