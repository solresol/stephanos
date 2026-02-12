PANDOC ?= pandoc
XELATEX ?= xelatex
BUILD_DIR ?= build

CLASSICAL_MD := classical_review_draft.md
COMPUTING_TEX := computing_venue_draft.tex

CLASSICAL_PDF := $(BUILD_DIR)/classical_review_draft.pdf
CLASSICAL_DOCX := $(BUILD_DIR)/classical_review_draft.docx
COMPUTING_PDF := $(BUILD_DIR)/computing_venue_draft.pdf

.PHONY: all help computing-pdf classical-pdf classical-docx clean

all: computing-pdf classical-pdf classical-docx

help:
	@echo "Targets:"
	@echo "  make computing-pdf   Build computing paper PDF from LaTeX"
	@echo "  make classical-pdf   Build classical paper PDF from Markdown"
	@echo "  make classical-docx  Build classical paper Word document from Markdown"
	@echo "  make all             Build all outputs into $(BUILD_DIR)/"
	@echo "  make clean           Remove generated outputs"

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

computing-pdf: $(COMPUTING_PDF)

$(COMPUTING_PDF): $(COMPUTING_TEX) | $(BUILD_DIR)
	$(XELATEX) -interaction=nonstopmode -halt-on-error -output-directory $(BUILD_DIR) $(COMPUTING_TEX)
	$(XELATEX) -interaction=nonstopmode -halt-on-error -output-directory $(BUILD_DIR) $(COMPUTING_TEX)

classical-pdf: $(CLASSICAL_PDF)

$(CLASSICAL_PDF): $(CLASSICAL_MD) | $(BUILD_DIR)
	$(PANDOC) $(CLASSICAL_MD) --from gfm --standalone --pdf-engine=xelatex --output $@

classical-docx: $(CLASSICAL_DOCX)

$(CLASSICAL_DOCX): $(CLASSICAL_MD) | $(BUILD_DIR)
	$(PANDOC) $(CLASSICAL_MD) --from gfm --to docx --standalone --output $@

clean:
	rm -rf $(BUILD_DIR)
