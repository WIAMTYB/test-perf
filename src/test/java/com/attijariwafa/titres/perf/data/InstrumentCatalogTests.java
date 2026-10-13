package com.attijariwafa.titres.perf.data;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class InstrumentCatalogTests {

    @Test
    void readsPricedActiveAssetsOnly() {
        String body = """
                [
                  {"isin":"MA0000011884","active":true,"symbol":"BCP","price":335.5,"priceDate":"2026-10-08T00:00:00","marketData":{"lastPrice":336.0}},
                  {"isin":"MA0000011454","active":true,"symbol":"CIH","price":null},
                  {"isin":"MA0000012445","active":false,"symbol":"IAM","price":120.0},
                  {"isin":"MA0000011512","symbol":"BOA","price":"40.25"}
                ]
                """;
        Map<String, BigDecimal> prices = InstrumentCatalog.parsePrices(body);

        assertThat(prices).containsOnlyKeys("MA0000011884", "MA0000011512");
        assertThat(prices.get("MA0000011884")).isEqualByComparingTo("335.5");
        assertThat(prices.get("MA0000011512")).isEqualByComparingTo("40.25");
    }
}
