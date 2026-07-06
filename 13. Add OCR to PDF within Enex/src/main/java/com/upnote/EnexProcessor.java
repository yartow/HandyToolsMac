package com.upnote;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerException;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Processes a single .enex file: extracts PDF text and injects it into each note's content. */
final class EnexProcessor {

    private static final Pattern XML_DECL = Pattern.compile("^\\s*<\\?xml[^>]*\\?>");
    private static final Pattern DOCTYPE = Pattern.compile("<!DOCTYPE[^>]*>");

    private final PdfTextExtractor extractor = new PdfTextExtractor();

    void process(Path inputEnex, Path outputEnex) throws IOException, ParserConfigurationException, SAXException, TransformerException {
        String raw = Files.readString(inputEnex, StandardCharsets.UTF_8);
        String xmlDecl = extractXmlDeclaration(raw);
        String doctype = extractDoctype(raw);

        Document doc = parse(raw);
        NodeList notes = doc.getElementsByTagName("note");

        int pdfCount = 0;
        int ocrCount = 0;
        int blankCount = 0;
        for (int i = 0; i < notes.getLength(); i++) {
            Counters c = processNote((Element) notes.item(i), doc);
            pdfCount += c.pdfs;
            ocrCount += c.ocr;
            blankCount += c.blank;
        }

        System.out.printf("[DONE] %s: %d notes, %d PDFs, %d used OCR, %d still blank%n",
                inputEnex.getFileName(), notes.getLength(), pdfCount, ocrCount, blankCount);

        String body = serializeRoot(doc);
        String finalXml = xmlDecl + "\n" + doctype + "\n" + body;
        atomicWrite(outputEnex, finalXml);
    }

    private record Counters(int pdfs, int ocr, int blank) {
    }

    private Counters processNote(Element noteEl, Document doc) {
        Element contentEl = firstChildElement(noteEl, "content");
        if (contentEl == null) {
            return new Counters(0, 0, 0);
        }

        List<Element> pdfResources = new ArrayList<>();
        for (Element resource : childElements(noteEl, "resource")) {
            Element mimeEl = firstChildElement(resource, "mime");
            if (mimeEl != null && "application/pdf".equals(mimeEl.getTextContent().trim())) {
                pdfResources.add(resource);
            }
        }
        if (pdfResources.isEmpty()) {
            return new Counters(0, 0, 0);
        }

        String noteTitle = titleOf(noteEl);
        List<String> fragments = new ArrayList<>();
        int ocrCount = 0;
        int blankCount = 0;
        int index = 0;
        for (Element resource : pdfResources) {
            index++;
            String fileName = fileNameOf(resource, index);
            String label = noteTitle + " / " + fileName;

            byte[] pdfBytes = decodeResourceData(resource);
            if (pdfBytes == null) {
                System.err.println("    [WARN] Could not decode PDF data for " + label);
                continue;
            }

            PdfTextExtractor.Result result = extractor.extractWithOcrFallback(pdfBytes, label);
            if (result.usedOcr()) {
                ocrCount++;
            }
            if (result.text().trim().isEmpty()) {
                blankCount++;
                System.err.println("    [WARN] No text could be extracted from " + label + " even after OCR");
                continue;
            }
            fragments.add(EnexContentInjector.buildFragment(fileName, result.text()));
        }

        if (!fragments.isEmpty()) {
            String innerXml = contentEl.getTextContent();
            String updated = EnexContentInjector.injectBeforeClosingTag(innerXml, fragments);
            EnexContentInjector.setContentAsCdata(doc, contentEl, updated);
        }

        return new Counters(pdfResources.size(), ocrCount, blankCount);
    }

    private static String titleOf(Element noteEl) {
        Element titleEl = firstChildElement(noteEl, "title");
        return titleEl != null ? titleEl.getTextContent().trim() : "(untitled note)";
    }

    private static String fileNameOf(Element resource, int index) {
        Element attrs = firstChildElement(resource, "resource-attributes");
        if (attrs != null) {
            Element fileNameEl = firstChildElement(attrs, "file-name");
            if (fileNameEl != null && !fileNameEl.getTextContent().isBlank()) {
                return fileNameEl.getTextContent().trim();
            }
        }
        return "attachment-" + index + ".pdf";
    }

    private static byte[] decodeResourceData(Element resource) {
        Element dataEl = firstChildElement(resource, "data");
        if (dataEl == null) {
            return null;
        }
        try {
            return Base64.getMimeDecoder().decode(dataEl.getTextContent().trim());
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static Element firstChildElement(Element parent, String tagName) {
        for (Element child : childElements(parent, tagName)) {
            return child;
        }
        return null;
    }

    private static List<Element> childElements(Element parent, String tagName) {
        List<Element> result = new ArrayList<>();
        NodeList children = parent.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (node.getNodeType() == Node.ELEMENT_NODE && tagName.equals(node.getNodeName())) {
                result.add((Element) node);
            }
        }
        return result;
    }

    private static String extractXmlDeclaration(String raw) {
        Matcher m = XML_DECL.matcher(raw);
        return m.find() ? m.group() : "<?xml version=\"1.0\" encoding=\"UTF-8\"?>";
    }

    private static String extractDoctype(String raw) {
        Matcher m = DOCTYPE.matcher(raw);
        return m.find() ? m.group()
                : "<!DOCTYPE en-export SYSTEM \"http://xml.evernote.com/pub/export2.dtd\">";
    }

    private static Document parse(String raw) throws ParserConfigurationException, IOException, SAXException {
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        dbf.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        dbf.setFeature("http://xml.org/sax/features/external-general-entities", false);
        dbf.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        dbf.setXIncludeAware(false);
        dbf.setExpandEntityReferences(false);
        dbf.setCoalescing(false);
        dbf.setNamespaceAware(false);
        DocumentBuilder builder = dbf.newDocumentBuilder();
        builder.setEntityResolver((publicId, systemId) -> new org.xml.sax.InputSource(new ByteArrayInputStream(new byte[0])));
        return builder.parse(new ByteArrayInputStream(raw.getBytes(StandardCharsets.UTF_8)));
    }

    private static String serializeRoot(Document doc) throws TransformerException {
        Transformer transformer = TransformerFactory.newInstance().newTransformer();
        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
        transformer.setOutputProperty(OutputKeys.CDATA_SECTION_ELEMENTS, "content");
        transformer.setOutputProperty(OutputKeys.ENCODING, "UTF-8");
        transformer.setOutputProperty(OutputKeys.INDENT, "no");
        StringWriter writer = new StringWriter();
        transformer.transform(new DOMSource(doc), new StreamResult(writer));
        return writer.toString();
    }

    private static void atomicWrite(Path outputEnex, String content) throws IOException {
        Path parent = outputEnex.toAbsolutePath().getParent();
        Files.createDirectories(parent);
        Path tmp = Files.createTempFile(parent, "." + outputEnex.getFileName(), ".tmp");
        try {
            Files.writeString(tmp, content, StandardCharsets.UTF_8);
            Files.move(tmp, outputEnex, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException e) {
            Files.deleteIfExists(tmp);
            throw e;
        }
    }
}
