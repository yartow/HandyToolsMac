package com.upnote;

import org.w3c.dom.CDATASection;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

import java.util.ArrayList;
import java.util.List;

/**
 * Handles the CDATA-safe surgery needed to append extracted PDF text into a
 * note's {@code <content>} element.
 *
 * <p>A note's {@code <content>} holds one CDATA blob whose character data is
 * itself a second XML document: {@code <!DOCTYPE en-note ...><en-note>...</en-note>}.
 * We insert the new text as a string, just before the closing {@code </en-note>}
 * tag, rather than parsing that inner document with a second DOM parser.
 */
final class EnexContentInjector {

    private EnexContentInjector() {
    }

    static String xmlEscape(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    static String buildFragment(String fileName, String extractedText) {
        StringBuilder sb = new StringBuilder();
        sb.append("<div><br/></div><div>--- Extracted text from: ")
          .append(xmlEscape(fileName)).append(" ---</div>");
        for (String line : extractedText.split("\n", -1)) {
            if (line.isBlank()) {
                sb.append("<div><br/></div>");
            } else {
                sb.append("<div>").append(xmlEscape(line)).append("</div>");
            }
        }
        return sb.toString();
    }

    /**
     * Inserts one or more pre-built fragments just before {@code </en-note>}.
     * If the closing tag can't be found (malformed note), appends at the end
     * instead of dropping the extracted text.
     */
    static String injectBeforeClosingTag(String innerXml, List<String> fragments) {
        if (fragments.isEmpty()) {
            return innerXml;
        }
        String toInsert = String.join("", fragments);
        int idx = innerXml.lastIndexOf("</en-note>");
        if (idx < 0) {
            System.err.println("    [WARN] </en-note> not found; appending extracted text at end instead");
            return innerXml + toInsert;
        }
        return innerXml.substring(0, idx) + toInsert + innerXml.substring(idx);
    }

    /**
     * Splits a string on every literal {@code ]]>} so that no resulting chunk
     * contains that sequence. Concatenating the chunks reproduces the original
     * string exactly; each chunk is safe to store in its own CDATASection.
     */
    static List<String> splitCdataSafe(String data) {
        List<String> chunks = new ArrayList<>();
        int start = 0;
        int idx;
        while ((idx = data.indexOf("]]>", start)) != -1) {
            chunks.add(data.substring(start, idx + 2)); // keep the two ']' chars in this chunk
            start = idx + 2;                            // next chunk starts at the '>'
        }
        chunks.add(data.substring(start));
        return chunks;
    }

    static void setContentAsCdata(Document doc, Element contentEl, String newValue) {
        while (contentEl.hasChildNodes()) {
            contentEl.removeChild(contentEl.getFirstChild());
        }
        for (String chunk : splitCdataSafe(newValue)) {
            CDATASection section = doc.createCDATASection(chunk);
            contentEl.appendChild(section);
        }
    }
}
