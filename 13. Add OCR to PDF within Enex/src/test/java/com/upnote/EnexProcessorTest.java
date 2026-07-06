package com.upnote;

import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertTrue;

class EnexProcessorTest {

    @Test
    void process_digitalPdf_getsTextAppendedDirectly(@TempDir Path tempDir) throws Exception {
        Path input = tempDir.resolve("sample.enex");
        Files.writeString(input, FixtureGenerator.buildSampleEnex(), StandardCharsets.UTF_8);
        Path output = tempDir.resolve("sample-out.enex");

        new EnexProcessor().process(input, output);

        String result = Files.readString(output, StandardCharsets.UTF_8);
        assertTrue(result.startsWith("<?xml"), "output should start with an XML declaration");
        assertTrue(result.contains("<!DOCTYPE en-export"), "output should preserve the en-export DOCTYPE");
        assertTrue(result.contains("Extracted text from: digital.pdf"));
        assertTrue(result.contains("This is a digital, text-based PDF."));
    }

    @Test
    void process_scannedPdf_usesOcrFallbackWhenAvailable(@TempDir Path tempDir) throws Exception {
        Assumptions.assumeTrue(isOcrMyPdfOnPath(), "ocrmypdf not installed on this machine; OCR path only verified in Docker");

        Path input = tempDir.resolve("sample.enex");
        Files.writeString(input, FixtureGenerator.buildSampleEnex(), StandardCharsets.UTF_8);
        Path output = tempDir.resolve("sample-out.enex");

        new EnexProcessor().process(input, output);

        String result = Files.readString(output, StandardCharsets.UTF_8);
        assertTrue(result.contains("Extracted text from: scanned.pdf"));
    }

    private static boolean isOcrMyPdfOnPath() {
        try {
            Process p = new ProcessBuilder("ocrmypdf", "--version").start();
            return p.waitFor() == 0;
        } catch (IOException | InterruptedException e) {
            return false;
        }
    }
}
