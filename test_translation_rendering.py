#!/usr/bin/env python3
import unittest

from translation_rendering import split_translation_blocks


class TranslationRenderingTests(unittest.TestCase):
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
