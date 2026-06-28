# syntax=docker/dockerfile:1
# Single Dockerfile used to build all four services.
# Pick which one with: docker build --build-arg SERVICE=order-service -t order-service:local .

# ---------- Stage 1: build the whole Maven reactor once ----------
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /workspace
COPY pom.xml .
COPY common/pom.xml common/pom.xml
COPY services/gateway-service/pom.xml services/gateway-service/pom.xml
COPY services/order-service/pom.xml services/order-service/pom.xml
COPY services/product-service/pom.xml services/product-service/pom.xml
COPY services/payment-service/pom.xml services/payment-service/pom.xml
# Warm the dependency cache (cached layer + BuildKit ~/.m2 cache mount).
RUN --mount=type=cache,target=/root/.m2 mvn -B -q dependency:go-offline || true
COPY common common
COPY services services
RUN --mount=type=cache,target=/root/.m2 mvn -B -q clean package -DskipTests

# ---------- Stage 2: slim runtime with the OpenTelemetry agent ----------
FROM eclipse-temurin:17-jre
ARG SERVICE
ARG OTEL_AGENT_VERSION=2.10.0
WORKDIR /app

# Zero-code instrumentation: the agent auto-instruments Spring MVC, RestTemplate, JDBC, logback, etc.
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v${OTEL_AGENT_VERSION}/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar

COPY --from=build /workspace/services/${SERVICE}/target/${SERVICE}.jar /app/app.jar

ENTRYPOINT ["java", "-javaagent:/app/opentelemetry-javaagent.jar", "-jar", "/app/app.jar"]
