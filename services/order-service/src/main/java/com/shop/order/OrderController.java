package com.shop.order;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Order orchestration service. A single POST /orders fans out to product-service (price lookup +
 * stock reservation) and payment-service (charge). Because the OpenTelemetry agent propagates
 * trace-context on the outbound RestTemplate calls, the whole fan-out shows up as one trace with
 * child spans per downstream hop.
 */
@RestController
@RequestMapping("/orders")
public class OrderController {

    private static final Logger log = LoggerFactory.getLogger(OrderController.class);

    private final RestTemplate rest;
    private final String productUrl;
    private final String paymentUrl;
    private final Map<String, Order> orders = new ConcurrentHashMap<>();
    private final Counter createdCounter;
    private final Counter failedCounter;

    public OrderController(RestTemplate rest,
                           MeterRegistry registry,
                           @Value("${downstream.product-service.url}") String productUrl,
                           @Value("${downstream.payment-service.url}") String paymentUrl) {
        this.rest = rest;
        this.productUrl = productUrl;
        this.paymentUrl = paymentUrl;
        this.createdCounter = Counter.builder("shop.order.created")
                .description("Orders successfully placed").register(registry);
        this.failedCounter = Counter.builder("shop.order.failed")
                .description("Orders that failed (stock or payment)").register(registry);
    }

    @PostMapping
    public Order create(@RequestBody CreateOrderRequest req) {
        String orderId = "ord-" + UUID.randomUUID().toString().substring(0, 8);
        log.info("Creating order {} for product={} qty={}", orderId, req.productId(), req.quantity());

        // 1) Look up the product (price + existence) from product-service.
        Map<String, Object> product;
        try {
            product = rest.getForObject(productUrl + "/products/" + req.productId(), Map.class);
        } catch (HttpStatusCodeException e) {
            failedCounter.increment();
            log.warn("Product lookup failed for {}: {}", req.productId(), e.getStatusCode());
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid product " + req.productId());
        }
        double price = ((Number) product.get("price")).doubleValue();
        double amount = price * req.quantity();

        // 2) Reserve stock.
        try {
            rest.postForObject(productUrl + "/products/" + req.productId() + "/reserve",
                    Map.of("quantity", req.quantity()), Map.class);
        } catch (HttpStatusCodeException e) {
            failedCounter.increment();
            log.warn("Stock reservation failed for order {}: {}", orderId, e.getStatusCode());
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Out of stock");
        }

        // 3) Charge the customer.
        Map<String, Object> payment;
        try {
            payment = rest.postForObject(paymentUrl + "/payments",
                    Map.of("orderId", orderId, "amount", amount), Map.class);
        } catch (HttpStatusCodeException e) {
            failedCounter.increment();
            log.warn("Payment failed for order {}: {}", orderId, e.getStatusCode());
            throw new ResponseStatusException(HttpStatus.PAYMENT_REQUIRED, "Payment declined");
        }

        Order order = new Order(orderId, req.productId(), req.quantity(), amount,
                String.valueOf(payment.get("paymentId")), "CONFIRMED");
        orders.put(orderId, order);
        createdCounter.increment();
        log.info("Order {} CONFIRMED amount={} payment={}", orderId, amount, order.paymentId());
        return order;
    }

    @GetMapping("/{id}")
    public Order get(@PathVariable String id) {
        Order o = orders.get(id);
        if (o == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown order " + id);
        }
        return o;
    }

    public record CreateOrderRequest(String productId, int quantity) {
    }

    public record Order(String orderId, String productId, int quantity, double amount,
                        String paymentId, String status) {
    }
}
