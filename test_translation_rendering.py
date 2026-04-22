#!/usr/bin/env python3
import unittest

from translation_rendering import sanitize_public_translation_text, split_translation_blocks


class TranslationRenderingTests(unittest.TestCase):
    def test_parenthetical_text_is_preserved(self):
        text = (
            "Kyrnos: an island to the north of Iapygia. Hekataios in the *Europa*. "
            "They say that the Kyrnaioi are exceedingly long-lived "
            "(and these dwell around Sardona), because they make constant use of honey."
        )

        blocks = split_translation_blocks(text)

        self.assertEqual([block.kind for block in blocks], ["paragraph"])
        self.assertIn("(and these dwell around Sardona)", blocks[0].text)

    def test_bracketed_editorial_text_is_preserved(self):
        text = (
            "Dadokerta: a large fortress of Armenia, situated between Media and [lacuna]. "
            "The ethnic is Dadokertenos."
        )

        blocks = split_translation_blocks(text)

        self.assertEqual([block.kind for block in blocks], ["paragraph"])
        self.assertIn("[lacuna]", blocks[0].text)

    def test_public_sanitizer_preserves_content_aside_when_greek_has_matching_aside(self):
        text = (
            "Kyrnos: an island to the north of Iapygia. Hekataios in the *Europa*. "
            "They say that the Kyrnaioi are exceedingly long-lived "
            "(and these dwell around Sardona), because they make constant use of honey."
        )
        greek = "Κῦρνος νῆσος· Ἑκαταῖος Εὐρώπῃ. μακροβίους δὲ εἶναί φασι τοὺς Κυρναίους (οἰκοῦσι δὲ οὗτοι περὶ τὴν Σαρδόνα), διὰ τὸ μέλι χρῆσθαι συνεχῶς."

        sanitized = sanitize_public_translation_text(
            text,
            displayed_greek=greek,
            source_document="billerbeck",
        )

        self.assertIn("(and these dwell around Sardona)", sanitized)

    def test_public_sanitizer_removes_billerbeck_citation_parenthetical(self):
        text = "Kyrnos: an island to the north of Iapygia. Hekataios in the *Europa* (FGrHist 1 F 60)."

        sanitized = sanitize_public_translation_text(
            text,
            displayed_greek="Κῦρνος νῆσος· Ἑκαταῖος Εὐρώπῃ (FGrHist 1 F 60).",
            source_document="billerbeck",
        )

        self.assertNotIn("(FGrHist 1 F 60)", sanitized)
        self.assertEqual(sanitized, "Kyrnos: an island to the north of Iapygia. Hekataios in the *Europa*.")

    def test_public_sanitizer_removes_billerbeck_editorial_parenthetical(self):
        text = "Darapsa: a city in Arabia Felix (gentilic)."

        sanitized = sanitize_public_translation_text(
            text,
            displayed_greek="Δάραψα πόλις Εὐδαίμονος Ἀραβίας.",
            source_document="billerbeck",
        )

        self.assertNotIn("(gentilic)", sanitized)
        self.assertEqual(sanitized, "Darapsa: a city in Arabia Felix.")

    def test_public_sanitizer_removes_short_billerbeck_gloss_parenthetical(self):
        text = "Kanopos: it ought thus to be written (with π), though it is nevertheless written with β."

        sanitized = sanitize_public_translation_text(
            text,
            displayed_greek="Κάνωπος, οὕτως ἔδει γράφεσθαι [διὰ τοῦ « π ». γράφεται δὲ ὅμως] διὰ τοῦ « β ».",
            source_document="billerbeck",
        )

        self.assertNotIn("(with π)", sanitized)
        self.assertEqual(
            sanitized,
            "Kanopos: it ought thus to be written, though it is nevertheless written with β.",
        )

    def test_public_sanitizer_does_not_keep_parentheses_for_greek_bracket_aside(self):
        text = "Metachoion: from Oion 'from Oion' (Oion is a deme of Attica), as has been stated."

        sanitized = sanitize_public_translation_text(
            text,
            displayed_greek="Μετάχοιον ... ὡς τὸ ἐξ Οἴου, [Οἶον δὲ δῆμος τῆς Ἀττικῆς] ὡς λέλεκται.",
            source_document="billerbeck",
        )

        self.assertNotIn("(Oion is a deme of Attica)", sanitized)
        self.assertEqual(
            sanitized,
            "Metachoion: from Oion 'from Oion', as has been stated.",
        )

    def test_public_sanitizer_leaves_meineke_text_unchanged(self):
        text = "Dadokerta: a large fortress, situated between Media and [lacuna]."

        sanitized = sanitize_public_translation_text(
            text,
            displayed_greek="",
            source_document="meineke",
        )

        self.assertEqual(sanitized, text)

    def test_separate_single_quoted_terms_stay_in_prose(self):
        text = (
            "Kabalis: a city near Kibyra, to the south of the Maiandros. "
            "The genitive is 'Kabalidos'. A citizen is a 'Kabaleus'. Hekataios in his *Asia*.\n"
            "Also in the feminine, as Strabo in the said passage: \n"
            "'descendants of Lydians are the Kibyratai, of those who took possession of Kabalis'.\n"
            "But the polymath Alexandros says that the feminine is 'Kabalissa'. It is of the genus Olbia."
        )

        blocks = split_translation_blocks(text)

        self.assertEqual([block.kind for block in blocks], ["paragraph"])
        self.assertIn("'Kabalidos'. A citizen is a 'Kabaleus'.", blocks[0].text)
        self.assertIn(
            "'descendants of Lydians are the Kibyratai, of those who took possession of Kabalis'.",
            blocks[0].text,
        )

    def test_multiline_poetry_quote_survives_prior_single_line_quote(self):
        text = (
            'The citizen is *Milesios*. Thus he was called “Milesian”. The following is inscribed for him: '
            "“Fatherland Miletos bears for the Muses the much-longed-for\n"
            "Timotheos, the skilful charioteer of the lyre.”"
        )

        blocks = split_translation_blocks(text)

        self.assertEqual([block.kind for block in blocks], ["paragraph", "verse"])
        self.assertEqual(
            blocks[0].text,
            'The citizen is *Milesios*. Thus he was called “Milesian”. The following is inscribed for him:',
        )
        self.assertEqual(
            blocks[1].text,
            "Fatherland Miletos bears for the Muses the much-longed-for\n"
            "Timotheos, the skilful charioteer of the lyre.",
        )


if __name__ == "__main__":
    unittest.main()
