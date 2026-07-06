I have a Java/Maven project called enex-pdf-textify in this directory. It extracts
text from PDF attachments inside Evernote .enex export files and injects that text
into each note's body, so notes become full-text searchable after importing into
UpNote, which doesn't index PDF attachment content.

Digital PDFs are extracted directly with Apache PDFBox. Scanned/image-only PDFs (no
text layer) are OCR'd automatically first via the `ocrmypdf` CLI (Tesseract OCR,
English + Dutch language packs) before extraction is retried — this is the "Add OCR"
part referenced by this folder's name.

Files:
- pom.xml
- src/main/java/com/upnote/EnexPdfTextify.java (CLI entry point: single-file or
  whole-folder mode, skip-if-output-newer-than-input resumability)
- src/main/java/com/upnote/EnexProcessor.java (per-file DOM parse/inject/serialize,
  DOCTYPE + XML-declaration preservation)
- src/main/java/com/upnote/EnexContentInjector.java (CDATA-safe text injection: escapes
  the inner en-note XML, splits on any literal `]]>` before writing back as CDATA)
- src/main/java/com/upnote/PdfTextExtractor.java (PDFBox extraction + OCR-fallback
  decision)
- src/main/java/com/upnote/OcrMyPdfRunner.java (ocrmypdf subprocess wrapper)
- src/test/java/com/upnote/FixtureGenerator.java (builds a synthetic text PDF and a
  synthetic image-only "scanned" PDF, assembles both into test-fixture/sample.enex)
- src/test/java/com/upnote/EnexContentInjectorTest.java, EnexProcessorTest.java
- Dockerfile (multi-stage: Maven build stage, Debian runtime stage with ocrmypdf +
  Tesseract + language packs + a JRE)
- README.md

Verified end-to-end:
1. `mvn package` builds cleanly; unit + integration tests pass (the OCR-path assertion
   is skipped outside Docker via a JUnit `Assumption`, since plain Maven images don't
   have `ocrmypdf` installed).
2. The built jar, run against `test-fixture/sample.enex` (one note with a real
   text-based PDF, one with an image-only PDF), produces valid XML with the original
   DOCTYPE and CDATA-wrapped `<content>`, and correctly appends extracted text to both
   notes.
3. `docker build` + `docker run` against the same fixture reproduce the same result,
   with the scanned note's text coming from the OCR fallback (confirmed via the
   `[INFO] ... running OCR fallback` / `[OCR] ... done in Ns` log lines).
4. Re-running against already-processed output prints `[SKIP] ... already up to date`;
   touching the input file causes it to reprocess — confirms the resumability behavior
   needed for multi-hour/day runs on a home server.
