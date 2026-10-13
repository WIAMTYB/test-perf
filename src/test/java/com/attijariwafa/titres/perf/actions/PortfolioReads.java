package com.attijariwafa.titres.perf.actions;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.AccountPool;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.Thresholds;
import io.gatling.javaapi.core.ChainBuilder;

import java.util.List;

import static io.gatling.javaapi.core.CoreDsl.StringBody;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

/**
 * The reads the mobile application makes around an order, all on the account the virtual
 * user owns ({@code #{secaccount}} / {@code #{cashaccount}} from the feeder).
 */
public final class PortfolioReads {

    private PortfolioReads() {
    }

    /** Valued positions of the user's own account: a cache hit within the 60 s TTL. */
    public static ChainBuilder listValuedHot() {
        return exec(http(Thresholds.LIST_VALUED_HOT)
                .get("/position/listvalued")
                .queryParam("secaccounts", "#{secaccount}")
                .check(status().in(200, 204)));
    }

    /** Valued positions of a random pair of pool accounts: a distinct cache key, mostly misses. */
    public static ChainBuilder listValuedCold() {
        return exec(session -> {
            List<AccountPool.Account> accounts = AccountPool.accounts();
            String first = accounts.get(CampaignContext.nextInt(accounts.size())).secAccount();
            String second = accounts.get(CampaignContext.nextInt(accounts.size())).secAccount();
            String key = first.equals(second) ? first : first + "," + second;
            return session.set("coldAccounts", key);
        }).exec(http(Thresholds.LIST_VALUED_COLD)
                .get("/position/listvalued")
                .queryParam("secaccounts", "#{coldAccounts}")
                .check(status().in(200, 204)));
    }

    public static ChainBuilder listOrders() {
        return exec(http(Thresholds.LIST_ORDERS)
                .get("/xcastrade/v2/listorders")
                .queryParam("secaccount", "#{secaccount}")
                .queryParam("skip", "0")
                .queryParam("take", "50")
                .check(status().in(200, 204)));
    }

    public static ChainBuilder secAccounts() {
        return exec(http(Thresholds.SEC_ACCOUNTS)
                .get("/secaccount/getbycashaccounts")
                .queryParam("cashaccounts", "#{cashaccount}")
                .check(status().in(200, 204)));
    }

    public static ChainBuilder tradableAssets() {
        return exec(http(Thresholds.TRADABLE_ASSETS)
                .get("/tradableasset/v2/listforxcastrade")
                .check(status().is(200)));
    }

    /** Synchronous PositionMinute call: its latency stands next to the saga's hold calls. */
    public static ChainBuilder cashBalances() {
        String caller = PerfConfig.get().cashCaller();
        return exec(http(Thresholds.CASH_BALANCES)
                .post("/cash/balances")
                .body(StringBody(session -> "{"
                        + "\"caller\":\"" + caller + "\","
                        + "\"compte\":\"" + session.getString("cashaccount") + "\","
                        + "\"correlationId\":null"
                        + "}")).asJson()
                .check(status().is(200))
                .check(jsonPath("$.returnCode").ofInt().is(0)));
    }
}
