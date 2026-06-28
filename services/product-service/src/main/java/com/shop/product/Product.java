package com.shop.product;

public record Product(String id, String name, double price, int stock) {

    public Product withStock(int newStock) {
        return new Product(id, name, price, newStock);
    }
}
