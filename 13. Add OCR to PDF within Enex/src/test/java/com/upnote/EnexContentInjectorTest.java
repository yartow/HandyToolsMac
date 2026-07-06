package com.upnote;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EnexContentInjectorTest {

    @Test
    void splitCdataSafe_noTerminator_returnsSingleChunk() {
        List<String> chunks = EnexContentInjector.splitCdataSafe("hello world");
        assertEquals(List.of("hello world"), chunks);
    }

    @Test
    void splitCdataSafe_withTerminator_splitsAndReconstructs() {
        String original = "before]]>after";
        List<String> chunks = EnexContentInjector.splitCdataSafe(original);
        assertEquals(List.of("before]]", ">after"), chunks);
        assertEquals(original, String.join("", chunks));
        for (String chunk : chunks) {
            assertFalse(chunk.contains("]]>"), "chunk must not contain the raw CDATA terminator: " + chunk);
        }
    }

    @Test
    void splitCdataSafe_withMultipleTerminators_neverEmitsRawTerminator() {
        String original = "a]]>b]]>c]]>d";
        List<String> chunks = EnexContentInjector.splitCdataSafe(original);
        assertEquals(original, String.join("", chunks));
        for (String chunk : chunks) {
            assertFalse(chunk.contains("]]>"));
        }
    }

    @Test
    void injectBeforeClosingTag_insertsBeforeClosingTag() {
        String inner = "<en-note><div>hi</div></en-note>";
        String result = EnexContentInjector.injectBeforeClosingTag(inner, List.of("<div>added</div>"));
        assertEquals("<en-note><div>hi</div><div>added</div></en-note>", result);
    }

    @Test
    void injectBeforeClosingTag_missingClosingTag_appendsAtEnd() {
        String inner = "<en-note><div>hi</div>";
        String result = EnexContentInjector.injectBeforeClosingTag(inner, List.of("<div>added</div>"));
        assertTrue(result.endsWith("<div>added</div>"));
    }

    @Test
    void buildFragment_escapesXmlSpecialCharacters() {
        String fragment = EnexContentInjector.buildFragment("a<b>&c.pdf", "line with <tag> & ampersand");
        assertTrue(fragment.contains("a&lt;b&gt;&amp;c.pdf"));
        assertTrue(fragment.contains("line with &lt;tag&gt; &amp; ampersand"));
        assertFalse(fragment.contains("<tag>"));
    }
}
