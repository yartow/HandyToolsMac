package com.upnote;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

import java.io.IOException;
import java.time.Duration;
import java.time.Instant;

/**
 * Extracts text from a PDF, falling back to OCR (via {@link OcrMyPdfRunner})
 * when the PDF has no usable text layer (i.e. it's a scan/image).
 */
final class PdfTextExtractor {

    /** Below this many non-whitespace characters, treat the PDF as scanned/image-only. */
    private static final int MIN_MEANINGFUL_CHARS = 20;

    record Result(String text, boolean usedOcr) {
    }

    Result extractWithOcrFallback(byte[] pdfBytes, String label) {
        String direct = extractText(pdfBytes);
        if (direct.trim().length() >= MIN_MEANINGFUL_CHARS) {
            return new Result(direct, false);
        }

        System.out.println("    [INFO] No text layer in " + label + " -- running OCR fallback...");
        Instant start = Instant.now();
        byte[] ocred = OcrMyPdfRunner.run(pdfBytes, label);
        if (ocred == null) {
            return new Result(direct, false);
        }
        String ocrText = extractText(ocred);
        long seconds = Duration.between(start, Instant.now()).toSeconds();
        System.out.printf("    [OCR] %s done in %ds%n", label, seconds);
        return new Result(ocrText, true);
    }

    String extractText(byte[] pdfBytes) {
        try (PDDocument document = Loader.loadPDF(pdfBytes)) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            return stripper.getText(document);
        } catch (IOException e) {
            System.err.println("    [WARN] PDFBox failed to parse PDF: " + e.getMessage());
            return "";
        }
    }
}
