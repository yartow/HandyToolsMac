package com.upnote;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Runs each PDF through the {@code ocrmypdf} CLI (Tesseract under the hood) to
 * add a text layer, so scanned/image-only PDFs can be re-extracted with PDFBox.
 *
 * <p>Only available inside the Docker image, which installs ocrmypdf and its
 * native dependencies. If the binary isn't on PATH, callers see a null result
 * and fall back to the original (empty) text -- the tool still runs without it,
 * just without OCR.
 */
final class OcrMyPdfRunner {

    private static final long TIMEOUT_SECONDS = 30 * 60;
    private static final String LANGUAGES = "eng+nld";

    private OcrMyPdfRunner() {
    }

    static byte[] run(byte[] inputPdfBytes, String label) {
        Path tmpDir;
        try {
            tmpDir = Files.createTempDirectory("enex-ocr-");
        } catch (IOException e) {
            System.err.println("    [WARN] Could not create temp dir for OCR of " + label + ": " + e.getMessage());
            return null;
        }
        try {
            Path inFile = tmpDir.resolve("input.pdf");
            Path outFile = tmpDir.resolve("output.pdf");
            Files.write(inFile, inputPdfBytes);

            List<String> command = List.of(
                    "ocrmypdf",
                    "--language", LANGUAGES,
                    "--skip-text",
                    "--rotate-pages",
                    "--deskew",
                    "--quiet",
                    inFile.toString(), outFile.toString());

            Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
            String log = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);

            boolean finished = process.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                System.err.println("    [WARN] ocrmypdf timed out for " + label);
                return null;
            }
            if (process.exitValue() != 0 || !Files.exists(outFile)) {
                System.err.println("    [WARN] ocrmypdf failed (exit " + process.exitValue() + ") for " + label
                        + (log.isBlank() ? "" : ": " + log.trim()));
                return null;
            }
            return Files.readAllBytes(outFile);
        } catch (IOException e) {
            System.err.println("    [WARN] ocrmypdf invocation failed for " + label
                    + " (is ocrmypdf installed?): " + e.getMessage());
            return null;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            System.err.println("    [WARN] ocrmypdf invocation interrupted for " + label);
            return null;
        } finally {
            deleteRecursively(tmpDir);
        }
    }

    private static void deleteRecursively(Path dir) {
        try (var stream = Files.walk(dir)) {
            stream.sorted(Comparator.reverseOrder()).forEach(p -> {
                try {
                    Files.deleteIfExists(p);
                } catch (IOException e) {
                    throw new UncheckedIOException(e);
                }
            });
        } catch (IOException | UncheckedIOException e) {
            System.err.println("    [WARN] Failed to clean up temp dir " + dir + ": " + e.getMessage());
        }
    }
}
