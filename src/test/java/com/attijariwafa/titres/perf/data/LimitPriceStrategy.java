package com.attijariwafa.titres.perf.data;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Limit prices that rest in the order book: a buy well under the reference, a sell well
 * above it, both inside the validation band so the order reaches the broker but does not
 * execute. Rounded to the instrument's tick, two decimals, as the API accepts.
 */
public final class LimitPriceStrategy {

    private LimitPriceStrategy() {
    }

    public static BigDecimal buy(BigDecimal referencePrice, double offsetPercent, BigDecimal tickSize) {
        BigDecimal factor = BigDecimal.ONE.subtract(BigDecimal.valueOf(offsetPercent).movePointLeft(2));
        return roundToTick(referencePrice.multiply(factor), tickSize, RoundingMode.UP);
    }

    public static BigDecimal sell(BigDecimal referencePrice, double offsetPercent, BigDecimal tickSize) {
        BigDecimal factor = BigDecimal.ONE.add(BigDecimal.valueOf(offsetPercent).movePointLeft(2));
        return roundToTick(referencePrice.multiply(factor), tickSize, RoundingMode.DOWN);
    }

    /** Rounds towards the reference price so the result can never leave the band. */
    static BigDecimal roundToTick(BigDecimal price, BigDecimal tickSize, RoundingMode mode) {
        BigDecimal ticks = price.divide(tickSize, 0, mode);
        return ticks.multiply(tickSize).setScale(2, RoundingMode.HALF_UP);
    }
}
