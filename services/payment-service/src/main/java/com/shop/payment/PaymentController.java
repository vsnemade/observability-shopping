package com.shop.payment;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Payment service. A leaf service that simulates a real payment gateway: variable latency plus an
 * occasional decline, which makes the latency histograms and error-rate metrics interesting and
 * produces traces with both success and error spans.
 */
@RestController
@RequestMapping("/payments")
public class PaymentController {

    private static final Logger log = LoggerFactory.getLogger(PaymentController.class);

    private final MeterRegistry registry;
    private final Timer processingTimer;

    public PaymentController(MeterRegistry registry) {
        this.registry = registry;
        this.processingTimer = Timer.builder("shop.payment.processing")
                .description("Time spent talking to the (simulated) payment gateway")
                .publishPercentileHistogram()
                .register(registry);
    }

    @PostMapping
    public PaymentResponse pay(@RequestBody PaymentRequest req) {
        return processingTimer.record(() -> doPay(req));
    }

    private PaymentResponse doPay(PaymentRequest req) {
        // Simulate gateway latency: usually fast, sometimes slow.
        long latencyMs = ThreadLocalRandom.current().nextLong(20, 120);
        if (ThreadLocalRandom.current().nextInt(100) < 10) {
            latencyMs += ThreadLocalRandom.current().nextLong(300, 700); // slow tail ~10% of the time
        }
        sleep(latencyMs);

        // ~8% of charges are declined -> drives the error-rate metric and error spans.
        boolean declined = ThreadLocalRandom.current().nextInt(100) < 8;
        if (declined) {
            registry.counter("shop.payment.result", "status", "declined").increment();
            log.warn("Payment DECLINED for order {} amount {}", req.orderId(), req.amount());
            throw new ResponseStatusException(HttpStatus.PAYMENT_REQUIRED, "Card declined");
        }

        String paymentId = "pay-" + UUID.randomUUID().toString().substring(0, 8);
        registry.counter("shop.payment.result", "status", "approved").increment();
        log.info("Payment APPROVED id={} order={} amount={} latencyMs={}",
                paymentId, req.orderId(), req.amount(), latencyMs);
        return new PaymentResponse(paymentId, req.orderId(), req.amount(), "APPROVED");
    }

    private void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public record PaymentRequest(String orderId, double amount) {
    }

    public record PaymentResponse(String paymentId, String orderId, double amount, String status) {
    }
}
