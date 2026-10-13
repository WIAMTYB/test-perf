package com.attijariwafa.titres.perf.actions;

import com.attijariwafa.titres.perf.config.PerfConfig;
import com.attijariwafa.titres.perf.data.CampaignRefs;
import com.attijariwafa.titres.perf.data.InstrumentCatalog;
import com.attijariwafa.titres.perf.data.LimitPriceStrategy;
import com.attijariwafa.titres.perf.support.AbortGuard;
import com.attijariwafa.titres.perf.support.CampaignContext;
import com.attijariwafa.titres.perf.support.Thresholds;
import io.gatling.javaapi.core.ChainBuilder;

import java.math.BigDecimal;
import java.util.List;

import static io.gatling.javaapi.core.CoreDsl.StringBody;
import static io.gatling.javaapi.core.CoreDsl.doIf;
import static io.gatling.javaapi.core.CoreDsl.exec;
import static io.gatling.javaapi.core.CoreDsl.jsonPath;
import static io.gatling.javaapi.http.HttpDsl.http;
import static io.gatling.javaapi.http.HttpDsl.status;

/**
 * {@code POST /xcastrade/book}: a resting limit order on one of the catalog's instruments,
 * for the account the virtual user owns. Session keys written: {@code clientReference},
 * {@code isin}, {@code side}, {@code price}, {@code bookedAt}, {@code bookStatus},
 * {@code bookReturnCode}, {@code mainReference}, {@code bookError}.
 *
 * <p>HTTP 409 is the API's per account and ISIN lock: it is a legitimate answer under
 * contention and is counted apart ({@code bookConflict}) rather than as a failure.
 * A 200 whose {@code returnCode} is not 0/200 is a business refusal and fails the request.
 */
public final class Book {

    private Book() {
    }

    public static ChainBuilder buy() {
        return bySide("BUY");
    }

    public static ChainBuilder sell() {
        return bySide("SELL");
    }

    /** Side from {@code -Dperf.side} (BUY by default). */
    public static ChainBuilder configuredSide() {
        return bySide(PerfConfig.get().side());
    }

    public static ChainBuilder bySide(String side) {
        boolean buy = !"SELL".equalsIgnoreCase(side);
        return exec(session -> {
            PerfConfig config = PerfConfig.get();
            List<InstrumentCatalog.Instrument> instruments = InstrumentCatalog.instruments();
            InstrumentCatalog.Instrument instrument = pick(instruments, session.getString("sellIsins"), buy);
            BigDecimal price = buy
                    ? LimitPriceStrategy.buy(instrument.referencePrice(), config.priceOffsetPercent(), instrument.tickSize())
                    : LimitPriceStrategy.sell(instrument.referencePrice(), config.priceOffsetPercent(), instrument.tickSize());
            long userIndex = session.contains("userIndex") ? session.getLong("userIndex") : CampaignContext.nextUserIndex();
            String reference = CampaignRefs.clientReference(config.campaignId(), userIndex, CampaignContext.nextSequence());
            boolean allowed = AbortGuard.allowOrder();
            return session
                    .set("userIndex", userIndex)
                    .set("clientReference", reference)
                    .set("isin", instrument.isin())
                    .set("side", buy ? "Buy" : "Sell")
                    .set("price", price.toPlainString())
                    .set("quantity", config.quantity())
                    .set("orderAllowed", allowed)
                    .set("bookedAt", System.currentTimeMillis())
                    .set("bookStatus", 0)
                    .set("bookReturnCode", "")
                    .set("mainReference", "")
                    .set("bookError", "")
                    .set("bookConflict", false);
        }).doIf(session -> session.getBoolean("orderAllowed")).then(
                exec(http(Thresholds.BOOK)
                        .post("/xcastrade/book")
                        .body(StringBody(Book::body)).asJson()
                        .check(status().in(200, 409).saveAs("bookStatus"))
                        .check(jsonPath("$.mainReference").optional().saveAs("mainReference"))
                        .check(jsonPath("$.errorMessage").optional().saveAs("bookError"))
                        .checkIf((response, session) -> response.status().code() == 200)
                        .then(jsonPath("$.returnCode").ofInt().in(0, 200).saveAs("bookReturnCode")))
                .exec(session -> session.set("bookConflict", session.getInt("bookStatus") == 409)));
    }

    private static InstrumentCatalog.Instrument pick(List<InstrumentCatalog.Instrument> instruments, String sellIsins, boolean buy) {
        if (!buy && sellIsins != null && !sellIsins.isBlank()) {
            // A sell needs a position: the account's own list wins over the catalog.
            String[] owned = sellIsins.split("\\|");
            String isin = owned[CampaignContext.nextInt(owned.length)];
            for (InstrumentCatalog.Instrument instrument : instruments) {
                if (instrument.isin().equals(isin)) {
                    return instrument;
                }
            }
            return InstrumentCatalog.byIsin(isin);
        }
        return instruments.get(CampaignContext.nextInt(instruments.size()));
    }

    static String body(io.gatling.javaapi.core.Session session) {
        return "{"
                + "\"clientReference\":\"" + session.getString("clientReference") + "\","
                + "\"clientSecAccount\":\"" + session.getString("secaccount") + "\","
                + "\"clientCashAccount\":\"" + session.getString("cashaccount") + "\","
                + "\"orderType\":\"" + session.getString("side") + "\","
                + "\"tradableAsset\":\"" + session.getString("isin") + "\","
                + "\"priceType\":\"Limit Price\","
                + "\"validityDate\":\"\","
                + "\"price\":" + session.getString("price") + ","
                + "\"quantity\":" + session.getInt("quantity") + ","
                + "\"source\":\"" + PerfConfig.get().source() + "\""
                + "}";
    }
}
