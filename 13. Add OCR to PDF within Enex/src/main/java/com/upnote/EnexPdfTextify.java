package com.upnote;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;

/**
 * CLI entry point. Makes PDF attachments inside Evernote .enex export files
 * full-text searchable (for import into UpNote) by extracting their text --
 * using OCR as a fallback for scanned/image-only PDFs -- and appending it to
 * each note's body.
 *
 * Usage:
 *   EnexPdfTextify <input.enex> <output.enex>       (single file)
 *   EnexPdfTextify <input-folder> <output-folder>   (every *.enex in the folder)
 */
public final class EnexPdfTextify {

    private EnexPdfTextify() {
    }

    public static void main(String[] args) {
        if (args.length != 2) {
            usage();
            System.exit(1);
        }
        Path in = Path.of(args[0]);
        Path out = Path.of(args[1]);

        if (!Files.exists(in)) {
            System.err.println("[ERROR] Input path does not exist: " + in);
            System.exit(1);
        }

        boolean ok = Files.isDirectory(in) ? processFolder(in, out) : processSingleFile(in, out);
        System.exit(ok ? 0 : 1);
    }

    private static boolean processFolder(Path inDir, Path outDir) {
        List<Path> enexFiles;
        try (Stream<Path> stream = Files.list(inDir)) {
            enexFiles = stream.filter(p -> p.toString().endsWith(".enex")).sorted().toList();
        } catch (IOException e) {
            System.err.println("[ERROR] Could not list input folder " + inDir + ": " + e.getMessage());
            return false;
        }

        if (enexFiles.isEmpty()) {
            System.out.println("[INFO] No *.enex files found in " + inDir);
            return true;
        }

        try {
            Files.createDirectories(outDir);
        } catch (IOException e) {
            System.err.println("[ERROR] Could not create output folder " + outDir + ": " + e.getMessage());
            return false;
        }

        boolean allOk = true;
        for (Path in : enexFiles) {
            Path out = outDir.resolve(in.getFileName());
            allOk &= processSingleFile(in, out);
        }
        return allOk;
    }

    private static boolean processSingleFile(Path in, Path out) {
        try {
            if (shouldSkip(in, out)) {
                System.out.println("[SKIP] " + in.getFileName() + " -- output already up to date");
                return true;
            }
            new EnexProcessor().process(in, out);
            return true;
        } catch (Exception e) {
            System.err.println("[ERROR] Failed to process " + in + ": " + e.getMessage());
            return false;
        }
    }

    private static boolean shouldSkip(Path in, Path out) throws IOException {
        return Files.exists(out)
                && Files.getLastModifiedTime(out).compareTo(Files.getLastModifiedTime(in)) >= 0;
    }

    private static void usage() {
        System.err.println("Usage:");
        System.err.println("  EnexPdfTextify <input.enex> <output.enex>       (single file)");
        System.err.println("  EnexPdfTextify <input-folder> <output-folder>   (every *.enex in the folder)");
    }
}
