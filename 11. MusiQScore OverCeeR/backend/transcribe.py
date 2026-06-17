#!/usr/bin/env python3

"""
MusiQScore OverCeeR — Claude vision transcription logic.
Converts an image file to LilyPond source code and optionally compiles it to PDF.
"""

import base64
import io
import os
import subprocess
import time
from pathlib import Path

import anthropic
from PIL import Image

# --------------------- CONFIG ---------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB — compress above this

# --------------------------------------------------

SYSTEM_PROMPT = """\
You are a music notation expert and LilyPond engraver. Transcribe the photographed
music sheet image into valid, compilable LilyPond 2.22 source code.

═══════════════════════════════════════════════════════
STRICT OUTPUT RULE
═══════════════════════════════════════════════════════
Respond with ONLY raw LilyPond code. No markdown fences, no explanations, no preamble.
The very first character must be a backslash (\\). The file must end with a closing brace.

═══════════════════════════════════════════════════════
REQUIRED FILE STRUCTURE (in this exact order)
═══════════════════════════════════════════════════════

\\version "2.22.0"
\\header {
  title = "TITLE HERE"
  tagline = ""
}
\\score {
  <<
    \\new ChordNames {
      \\chordmode { ... }
    }
    \\new Voice = "melody" {
      \\clef treble \\key f \\major \\time 4/4
      ... notes ...
    }
    \\new Lyrics \\lyricsto "melody" {
      Lyr -- ics here.
    }
  >>
  \\layout { }
}

The Voice MUST be named "melody" (\\new Voice = "melody") so \\lyricsto can reference it.
CRITICAL: Use \\new Lyrics \\lyricsto "melody" { ... } — do NOT put \\lyricmode after \\lyricsto.
\\lyricsto already enables lyric mode inside its braces.

═══════════════════════════════════════════════════════
TITLE
═══════════════════════════════════════════════════════
The user will specify a series prefix and any hints.
Extract the song number and title text from the image itself.
Build the header title as: "{prefix} {number} {song title}"
If no prefix: "{number} {song title}"

═══════════════════════════════════════════════════════
REPEATS — CRITICAL: use \\repeat volta, NOT \\volta
═══════════════════════════════════════════════════════
Section with 1st and 2nd endings:
  \\repeat volta 2 {
    ... shared measures ...
  }
  \\alternative {
    { ... 1st ending measures ... }
    { ... 2nd ending measures ... }
  }

Plain repeat (no alternative):  \\repeat volta 2 { ... }
D.C. al Fine:  write \\mark "D.C. al Fine" at the correct beat.
Fine:          write \\mark "Fine" at the correct beat.
Segno:         \\mark \\markup { \\musicglyph "scripts.segno" }

═══════════════════════════════════════════════════════
LYRICS — hyphenate with " -- " (space-hyphen-hyphen-space)
═══════════════════════════════════════════════════════
"Let there be praise"  →  Let there be praise,
"inhabits"             →  in -- hab -- its
"people"               →  peo -- ple
"glory"                →  glo -- ry
Held note / melisma    →  use _ for each additional note tied to that syllable
Verse separator        →  one \\new Lyrics block per verse with \\set stanza:

  \\new Lyrics \\lyricsto "melody" {
    \\set stanza = "1."
    First -- verse lyr -- ics ...
  }
  \\new Lyrics \\lyricsto "melody" {
    \\set stanza = "2."
    Sec -- ond -- verse lyr -- ics ...
  }

LilyPond assigns lyrics syllables sequentially to notes — write all syllables
in order as they would be sung on the first pass through the music.
Include ALL visible lyric lines from the image.

═══════════════════════════════════════════════════════
CHORD SYMBOLS in \\chordmode (duration before colon)
═══════════════════════════════════════════════════════
  F       → f1          Bb      → bes1         Eb → ees1
  Dm      → d1:m        Am      → a1:m          Gm → g1:m
  Gm7     → g1:m7       Dm7     → d1:m7         Am7 → a1:m7
  C7      → c1:7        G7      → g1:7          Bb7 → bes1:7
  Fmaj7   → f1:maj7     Bbmaj7  → bes1:maj7
  Csus    → c1:sus4     Fsus    → f1:sus4
  F/A     → f1/a        C/E     → c1/e          Bb/D → bes1/d
  Dm7b5   → d1:m7.5-

Chord duration matches the number of beats it lasts (1 = whole, 2 = half, 4 = quarter).

═══════════════════════════════════════════════════════
NOTE ACCURACY — read carefully, do not guess
═══════════════════════════════════════════════════════
- Count ledger lines above/below the staff for exact octave (middle C = c').
- Noteheads ON lines vs. IN spaces are different pitches — verify each one.
- Key signature applies throughout: Bb major → all B's are Bb, all E's are Eb.
- Stems up/down do NOT affect pitch.
- A beam connecting 4 noteheads = four 8th notes.
- Dot after a note = dotted rhythm (e.g. f4. = dotted quarter).
- Tie vs. slur: a tie connects two notes of the SAME pitch; use ~.
- When ambiguous: add % [ambiguous - inferred] on that line.
- Completely illegible measure: r1 % [illegible]

═══════════════════════════════════════════════════════
PHOTO QUALITY
═══════════════════════════════════════════════════════
Book curvature near the binding distorts the staff — compensate by checking
note position relative to clef and key signature rather than staff line angle.
Shadows may hide accidentals — infer from key and harmonic context.
Unclear time signature: default 4/4. Unclear key: default \\key c \\major.

ACCURACY OVER COMPLETENESS: A file that compiles with some placeholder rests
is more useful than one with syntax errors that crashes LilyPond.\
"""

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def image_to_base64(path: Path) -> tuple[str, str]:
    """Return (base64_string, media_type) for the given image file."""
    suffix = path.suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix, "image/jpeg")
    data = path.read_bytes()
    return base64.standard_b64encode(data).decode(), media_type


def compress_if_needed(path: Path) -> Path:
    """If image exceeds MAX_IMAGE_BYTES, recompress to JPEG in memory and save to a temp file."""
    if path.stat().st_size <= MAX_IMAGE_BYTES:
        return path

    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    quality = 80
    while quality >= 40:
        buf.seek(0)
        buf.truncate()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= MAX_IMAGE_BYTES:
            break
        quality -= 10

    tmp = path.parent / f"_compressed_{path.stem}.jpg"
    tmp.write_bytes(buf.getvalue())
    return tmp


def clean_lilypond_output(raw: str) -> tuple[str, str | None]:
    """
    Strip markdown fences, auto-correct known Claude mis-patterns, validate.
    Returns (cleaned_code, warning_message_or_None).
    """
    import re

    text = raw.strip()

    # Strip ```lilypond ... ``` or ``` ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        end = next((i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"), None)
        if end:
            text = "\n".join(lines[1:end]).strip()

    # \lyricsto already enables lyric mode — \lyricmode after it is a syntax error
    text = re.sub(r'(\\lyricsto\s+"[^"]+"\s*)\\lyricmode\b', r'\1', text)

    warning = None
    if not text.startswith("\\"):
        warning = "Output did not start with a backslash — may be malformed LilyPond"
        text = "% [WARNING: response may be malformed — review before compiling]\n" + text

    return text, warning


def transcribe_image(
    client: anthropic.Anthropic,
    image_path: Path,
    page_num: int,
    series_name: str = "",
) -> tuple[str, str | None]:
    """
    Send image to Claude and return (lilypond_code, warning_or_None).
    Retries once on RateLimitError.
    """
    compressed = compress_if_needed(image_path)
    is_temp = compressed != image_path

    try:
        b64, media_type = image_to_base64(compressed)
    finally:
        if is_temp and compressed.exists():
            compressed.unlink()

    prefix_line = (
        f"Series name prefix: \"{series_name}\" — prepend this to the title."
        if series_name
        else "No series name prefix — use just the number and title from the image."
    )

    user_prompt = (
        f"Transcribe the music in this image to LilyPond code.\n"
        f"This is page {page_num}. It is a lead sheet: treble clef melody only, "
        f"with chord symbols above the staff and lyrics below the staff.\n\n"
        f"{prefix_line}\n"
        f"Extract the song number and title visible in the image to build the \\header title.\n\n"
        f"Transcribe carefully:\n"
        f"  - Every note pitch and rhythm (count ledger lines, check key signature)\n"
        f"  - Every chord symbol above the staff\n"
        f"  - All lyrics below the staff, all verses, hyphenated correctly\n"
        f"  - Repeat signs, 1st/2nd endings, D.C., Fine, section marks\n\n"
        f"Output only the LilyPond code starting with \\version \"2.22.0\""
    )

    def _call() -> str:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }],
        )
        return response.content[0].text

    try:
        raw = _call()
    except anthropic.RateLimitError as e:
        retry_after = int(getattr(e, "response", None) and e.response.headers.get("retry-after", 60) or 60)
        print(f"      Rate limited — waiting {retry_after}s...")
        time.sleep(retry_after)
        raw = _call()

    return clean_lilypond_output(raw)


def compile_to_pdf(ly_path: Path, output_dir: Path) -> Path | None:
    """Run lilypond to compile .ly → .pdf. Returns PDF path or None on failure."""
    result = subprocess.run(
        ["lilypond", f"--output={output_dir / ly_path.stem}", str(ly_path)],
        capture_output=True,
        text=True,
    )
    pdf = output_dir / f"{ly_path.stem}.pdf"
    if result.returncode != 0 or not pdf.exists():
        print(f"      LilyPond error:\n{result.stderr[-500:]}")
        return None
    return pdf
