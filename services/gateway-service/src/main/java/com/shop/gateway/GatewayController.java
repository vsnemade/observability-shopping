package com.shop.gateway;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

/**
 * Public edge of the platform. Everything a "customer" does enters here, so a checkout request
 * produces a trace shaped like:
 *
 *   gateway POST /api/checkout
 *     └─ order POST /orders
 *          ├─ product GET /products/{id}
 *          ├─ product POST /products/{id}/reserve
 *          └─ payment POST /payments
 */
@RestController
@RequestMapping("/api")
public class GatewayController {

    private static final Logger log = LoggerFactory.getLogger(GatewayController.class);

    private final RestTemplate rest;
    private final String orderUrl;
    private final String productUrl;

    public GatewayController(RestTemplate rest,
                             @Value("${downstream.order-service.url}") String orderUrl,
                             @Value("${downstream.product-service.url}") String productUrl) {
        this.rest = rest;
        this.orderUrl = orderUrl;
        this.productUrl = productUrl;
    }

    @GetMapping("/products")
    public List<?> products() {
        log.info("Browsing catalog");
        return rest.getForObject(productUrl + "/products", List.class);
    }

    @PostMapping("/checkout")
    public Map<?, ?> checkout(@RequestBody Map<String, Object> body) {
        log.info("Checkout requested: {}", body);
        return rest.postForObject(orderUrl + "/orders", body, Map.class);
    }
}
