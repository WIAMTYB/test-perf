package com.attijariwafa.titres.perf.data;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class LimitPriceStrategyTests {

    private static final BigDecimal TICK = new BigDecimal("0.01");

    @Test
    void buyRestsBelowTheReferenceInsideTheBand() {
        // 30 % under a 335.50 close: 234.85, never below the 35 % band floor of 218.08
        assertThat(LimitPriceStrategy.buy(new BigDecimal("335.50"), 30, TICK)).isEqualByComparingTo("234.85");
    }

    @Test
    void sellRestsAboveTheReferenceInsideTheBand() {
        assertThat(LimitPriceStrategy.sell(new BigDecimal("335.50"), 30, TICK)).isEqualByComparingTo("436.15");
    }

    @Test
    void roundingNeverCrossesTheBandEdge() {
        // A coarse tick rounds towards the reference: up for a buy, down for a sell.
        BigDecimal tick = new BigDecimal("0.05");
        assertThat(LimitPriceStrategy.buy(new BigDecimal("100.03"), 30, tick)).isEqualByComparingTo("70.05");
        assertThat(LimitPriceStrategy.sell(new BigDecimal("100.03"), 30, tick)).isEqualByComparingTo("130.00");
    }

    @Test
    void twoDecimalsWhateverTheTick() {
        assertThat(LimitPriceStrategy.buy(new BigDecimal("12.3456"), 30, TICK).scale()).isEqualTo(2);
    }
}
