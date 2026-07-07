# --- Build stage: compiles the jar with Maven (downloads PDFBox) ---
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B package -DskipTests

# --- Runtime stage: Debian, not Alpine. ocrmypdf is a Python tool with a chain
# of native dependencies (Tesseract, Ghostscript, qpdf) that Debian's main
# archive ships directly; getting the same stack working on Alpine/musl is
# much more fragile, so the extra image size is worth it here. ---
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        ocrmypdf \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-nld \
        ghostscript \
        qpdf \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r enex && useradd -r -g enex -d /app enex

WORKDIR /app
COPY --from=build /build/target/enex-pdf-textify-1.0.jar app.jar
RUN mkdir -p /data/in /data/out && chown -R enex:enex /app /data/in /data/out
VOLUME ["/data/in", "/data/out"]

USER enex

# Expect input files under /data/in and output written to /data/out
# (mount your local folders there at `docker run` time)
ENTRYPOINT ["java", "-jar", "app.jar"]
CMD ["/data/in", "/data/out"]
