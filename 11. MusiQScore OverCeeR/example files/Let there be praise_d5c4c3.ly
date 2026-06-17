\version "2.22.0"
\header {
  title = "OTH 118 Let there be praise"
  tagline = ""
}
\score {
  <<
    \new ChordNames {
      \chordmode {
        % Refrein
        f2 f2 d2:m d2:m g2:m g2:m c2 c2
        a2:m a2:m d2:m d2:m
        % 1st ending
        ees2 ees2 c2:sus4 c2
        % 2nd ending
        g2:m7 f2 bes2 f2 c2:sus4 f4 f4:sus4 f2
        % Verse
        bes2 c2 f2 f2 bes2 c2 f2 f2
        bes2 c2 d2:m d2:m g2:m7 g2:m7
        c2:sus4 c2 a2 a2 d2:m d2:m g2:m7 g2:m7 c2:sus4 c2
        a2:m a2:m c2 c2 d2:m d2:m g2:m7 g2:m7 c2:sus4 c2
      }
    }
    \new Voice = "melody" {
      \clef treble \key f \major \time 4/4
      % Refrein
      \mark "Refrein"
      \repeat volta 2 {
        c''4 c''8 bes'8 a'4 f'4 f'4 g'8 a'8 bes'4 a'4
        g'4 g'8 f'8 g'4 a'4 g'2 r4 c''4
        c''4 c''8 bes'8 a'4 f'4 f'4 g'8 a'8 bes'4 a'4
      }
      \alternative {
        {
          g'4 g'8 f'8 g'4 a'8 g'8 f'2 r4 c''8 bes'8
        }
        {
          g'8 f'8 g'8 a'8 g'4 f'8 g'8 a'2~ a'4 r8 c''8
        }
      }
      % 2nd ending continuation / Fine
      f'8 g'8 a'4 bes'4 c''4 d''4 c''8 bes'8 a'4 g'2~ g'4
      r8 c''8 c''4 bes'8 a'8 g'2 \mark "Fine" r4 r8 c''8
      % Verse
      % Line 4: Bb C F Bb C F
      c''4 bes'8 a'8 g'4 f'4 f'4 g'4 a'4 bes'4
      c''4 bes'8 a'8 g'4 f'4 f'4 r4 r4 c''4
      % Line 5: Bb C Dm Gm7
      c''4 bes'8 a'8 g'4 f'4 f'4 g'4 a'4 bes'4
      c''4 c''4 d''4 c''4 bes'4 a'4 g'4 f'4
      % Line 6: Csus C A Dm Gm7 Csus C
      g'2 r4 c''4 c''4 d''4 e''4 f''4
      e''4 d''8 c''8 d''2~ d''4 r8 c''8
      c''4 bes'8 a'8 g'4 a'4 g'2 r4 c''8 bes'8
      % Line 7: Am C Dm Gm7 Csus C D.C.
      a'4 g'4 f'4 e'4 f'4 g'4 a'4 bes'4
      c''4 c''4 d''4 c''4 g'1~ g'1
      \mark "D.C."
    }
    \new Lyrics \lyricsto "melody" \lyricmode {
      \set stanza = "1."
      Let there be praise, let there be joy in our hearts.
      Sing to the Lord, give Him the glo -- ry. __
      fill the air and let there be praise. __
      He in -- hab -- its the praise of His peo -- ple, and dwells deep with -- in, __ the
      peace that He gives none can e -- qual, His love, it knows no end.
      So lift your voi -- ces, with glad -- ness sing,
      pro -- claim to all the earth that Je -- sus Christ is King! __
    }
    \new Lyrics \lyricsto "melody" \lyricmode {
      \set stanza = "2."
      Let there be praise, let there be joy in our hearts.
      Sing to the Lord, give Him the glo -- ry. __
      For ev -- er -- more, let His love __
      When the Spi -- rit of God is with -- in us, __ we will o -- ver -- come, __ in our
      weak -- ness, His strength will de -- fend us, when His praise is on our tongue.
      So lift your voi -- ces, with glad -- ness sing,
      pro -- claim to all the earth that Je -- sus Christ is King! __
    }
  >>
  \layout { }
}