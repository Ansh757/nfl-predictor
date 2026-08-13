# Build stage
# Note: the old `maven:3.8-openjdk-17` / `openjdk:17-jdk-slim` images were
# withdrawn from Docker Hub; Eclipse Temurin is the maintained replacement.
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app

# Copy pom.xml and download dependencies first for better layer caching
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source and build
COPY src ./src
RUN mvn clean package -DskipTests

# Runtime stage - JRE only, no compiler needed
FROM eclipse-temurin:17-jre-jammy
WORKDIR /app

COPY --from=build /app/target/*.jar app.jar

EXPOSE 8080

CMD ["java", "-jar", "app.jar"]
