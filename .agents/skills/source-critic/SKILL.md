---
name: source-critic
description: Verify the scope and transmission of cited authors, works, quotations, fragment references, and parallels for one Stephanos witness using structured citation evidence.
---

# Source critic

Read `../_shared/ledger-protocol.md` before acting.

Check each structured citation mention against the associated citation unit and
resolved quotation passage. Distinguish author identification, work
identification, passage numbering, direct quotation, paraphrase, verbal
parallel, and an unresolved traditional attribution.

For every positive finding, delimit what the named authority actually supports.
An author beside a place name may attest only that form, not the localization,
etymology, ethnic, or the rest of the entry. Distinguish these source relations
when the dossier supports them:

- direct quotation or close paraphrase;
- likely mediated excerpt;
- verbal or thematic parallel without demonstrated dependence;
- traditional attribution unresolved by the permitted evidence;
- unattributed wording that may preserve quotation residue.

Do not infer direct consultation merely from a named citation. Do not infer a
specific intermediary unless the supplied quotation evidence establishes the
relay. If abbreviation appears to have collapsed a citation chain, describe the
local scope problem and leave the broader redactional diagnosis to the Stephanos
specialist. Phrase claims about the surviving witness rather than about the lost
original unless the dossier contains evidence for the fuller layer.

Use these structured flags with `add-finding`:

- `--cited-author`
- `--cited-work`
- `--cited-reference`
- `--proposed-identification`
- `--parallel-reference`
- one or more `--citation-mention`
- one or more `--quote-passage`
- the relevant `--source-line`

Do not claim that a source is verified merely because an extraction model
created a citation row. A missing or unresolved passage is a negative or
uncertain result, not permission to invent a reference. Absence from the
surviving epitome does not establish absence from Stephanos' original. Avoid
the circular argument of reconstructing a lost source from this entry and then
using that reconstruction as independent proof of the entry.
