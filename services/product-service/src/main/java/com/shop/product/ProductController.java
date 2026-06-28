package com.shop.product;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Collection;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Catalog + stock service. This is a leaf service: it makes no downstream calls, so a trace that
 * reaches here ends with a span produced by this controller.
 */
@RestController
@RequestMapping("/products")
public class ProductController {

    private static final Logger log = LoggerFactory.getLogger(ProductController.class);

    private final Map<String, Product> catalog = new ConcurrentHashMap<>();
    private final Counter reservedCounter;
    private final Counter reserveFailureCounter;

    public ProductController(MeterRegistry registry) {
        // Custom business metrics — these appear in Prometheus alongside the auto http.server.requests.
        this.reservedCounter = Counter.builder("shop.product.reserved")
                .description("Number of successful stock reservations")
                .register(registry);
        this.reserveFailureCounter = Counter.builder("shop.product.reserve.failures")
                .description("Number of failed stock reservations (insufficient stock)")
                .register(registry);
        seed();
    }

    private void seed() {
        catalog.put("p-1", new Product("p-1", "Mechanical Keyboard", 89.99, 509000000));
        catalog.put("p-2", new Product("p-2", "27\" Monitor", 249.00, 30000000));
        catalog.put("p-3", new Product("p-3", "Wireless Mouse", 29.50, 10000000));
        catalog.put("p-4", new Product("p-4", "USB-C Hub", 45.00, 750000000));
    }

    @GetMapping
    public Collection<Product> list() {
        log.debug("Listing {} products", catalog.size());
        return catalog.values();
    }

    @GetMapping("/{id}")
    public Product get(@PathVariable String id) {
        Product p = catalog.get(id);
        if (p == null) {
            log.warn("Product {} not found", id);
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown product " + id);
        }
        log.debug("Fetched product {} (stock={})", id, p.stock());
        return p;
    }

    @PostMapping("/{id}/reserve")
    public ResponseEntity<Product> reserve(@PathVariable String id, @RequestBody ReserveRequest req) {
        Product p = catalog.get(id);
        if (p == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Unknown product " + id);
        }
        synchronized (this) {
            if (p.stock() < req.quantity()) {
                reserveFailureCounter.increment();
                log.warn("Insufficient stock for {}: requested={} available={}", id, req.quantity(), p.stock());
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Insufficient stock for " + id);
            }
            Product updated = p.withStock(p.stock() - req.quantity());
            catalog.put(id, updated);
            reservedCounter.increment(req.quantity());
            log.info("Reserved {} x {} (remaining stock={})", req.quantity(), id, updated.stock());
            return ResponseEntity.ok(updated);
        }
    }

    public record ReserveRequest(int quantity) {
    }
}
