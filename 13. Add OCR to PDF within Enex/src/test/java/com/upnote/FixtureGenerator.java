package com.upnote;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;

/**
 * Builds the synthetic test fixture: a "digital" PDF with a real text layer
 * (exercises direct PDFBox extraction) and a "scanned" PDF that is really
 * just a rasterized image of text with no text layer at all (exercises the
 * OCR fallback), then assembles both into a realistic sample.enex file.
 */
public final class FixtureGenerator {

    private FixtureGenerator() {
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            System.err.println("Usage: FixtureGenerator <output-path-for-sample.enex>");
            System.exit(1);
        }
        Path out = Path.of(args[0]);
        Files.createDirectories(out.toAbsolutePath().getParent());
        Files.writeString(out, buildSampleEnex(), StandardCharsets.UTF_8);
        System.out.println("Wrote fixture: " + out.toAbsolutePath());
    }

    static final String DIGITAL_PDF_TEXT = "This is a digital, text-based PDF.\nIt should be extracted directly by PDFBox.";
    static final String SCANNED_PDF_TEXT = "This is a scanned-look PDF.\nIt has no text layer, only an image.";

    public static String buildSampleEnex() throws IOException {
        byte[] digitalPdf = buildTextPdf(DIGITAL_PDF_TEXT);
        byte[] scannedPdf = buildScannedLookingPdf(SCANNED_PDF_TEXT);

        String note1 = buildNote("Digital note", "Body of the digital note.", "digital.pdf", digitalPdf);
        String note2 = buildNote("Scanned note", "Body of the scanned note.", "scanned.pdf", scannedPdf);

        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                + "<!DOCTYPE en-export SYSTEM \"http://xml.evernote.com/pub/export2.dtd\">\n"
                + "<en-export export-date=\"20260702T000000Z\" application=\"Quick Note\" version=\"10.0\">\n"
                + note1
                + note2
                + "</en-export>\n";
    }

    private static String buildNote(String title, String bodyText, String fileName, byte[] pdfBytes) {
        String innerXml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
                + "<!DOCTYPE en-note SYSTEM \"http://xml.evernote.com/pub/enml2.dtd\">"
                + "<en-note><div>" + EnexContentInjector.xmlEscape(bodyText) + "</div></en-note>";

        String base64 = Base64.getMimeEncoder(76, "\n".getBytes(StandardCharsets.US_ASCII))
                .encodeToString(pdfBytes);

        return "<note>"
                + "<title>" + EnexContentInjector.xmlEscape(title) + "</title>"
                + "<content><![CDATA[" + innerXml + "]]></content>"
                + "<created>20260702T000000Z</created>"
                + "<updated>20260702T000000Z</updated>"
                + "<resource>"
                + "<data encoding=\"base64\">\n" + base64 + "\n</data>"
                + "<mime>application/pdf</mime>"
                + "<resource-attributes><file-name>" + EnexContentInjector.xmlEscape(fileName) + "</file-name></resource-attributes>"
                + "</resource>"
                + "</note>";
    }

    static byte[] buildTextPdf(String text) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            doc.addPage(page);
            PDFont font = new PDType1Font(Standard14Fonts.FontName.HELVETICA);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.beginText();
                cs.setFont(font, 12);
                cs.newLineAtOffset(72, 700);
                for (String line : text.split("\n")) {
                    cs.showText(line);
                    cs.newLineAtOffset(0, -16);
                }
                cs.endText();
            }
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.save(bos);
            return bos.toByteArray();
        }
    }

    static byte[] buildScannedLookingPdf(String text) throws IOException {
        int width = 1700;
        int height = 2200; // ~8.5x11in at 200dpi
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = image.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, width, height);
        g.setColor(Color.BLACK);
        g.setFont(new Font("SansSerif", Font.PLAIN, 40));
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_OFF);
        int y = 200;
        for (String line : text.split("\n")) {
            g.drawString(line, 150, y);
            y += 60;
        }
        g.dispose();

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            doc.addPage(page);
            PDImageXObject pdImage = LosslessFactory.createFromImage(doc, image);
            float scale = PDRectangle.LETTER.getWidth() / width;
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.drawImage(pdImage, 0, 0, width * scale, height * scale);
            }
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            doc.save(bos);
            return bos.toByteArray();
        }
    }
}
