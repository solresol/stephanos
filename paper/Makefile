PANDOC ?= pandoc
XELATEX ?= xelatex
BUILD_DIR ?= build

CLASSICAL_MD := classical_review_draft.md
COMPUTING_TEX := computing_venue_draft.tex
BENCHMARK_MD := benchmark_translation_draft.md
BENCHMARK_TEX := $(BUILD_DIR)/benchmark_translation_draft.tex

CLASSICAL_PDF := $(BUILD_DIR)/classical_review_draft.pdf
CLASSICAL_DOCX := $(BUILD_DIR)/classical_review_draft.docx
COMPUTING_PDF := $(BUILD_DIR)/computing_venue_draft.pdf
BENCHMARK_PDF := ../output/pdf/stephanos_llm_translation_benchmark_draft.pdf

.PHONY: all help computing-pdf classical-pdf classical-docx benchmark-analysis neural-benchmark-analysis guidance-ablation-analysis benchmark-pdf clean

all: computing-pdf classical-pdf classical-docx

help:
	@echo "Targets:"
	@echo "  make computing-pdf   Build computing paper PDF from LaTeX"
	@echo "  make classical-pdf   Build classical paper PDF from Markdown"
	@echo "  make classical-docx  Build classical paper Word document from Markdown"
	@echo "  make neural-benchmark-analysis  Rebuild learned-metric tables from cached scores"
	@echo "  make guidance-ablation-analysis  Rebuild the controlled GPT-5.6 guidance ablation"
	@echo "  make benchmark-pdf   Rebuild benchmark data and compile the full benchmark paper"
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

benchmark-analysis:
	cd .. && DB_HOST=$${DB_HOST:-raksasa} DB_USER=$${DB_USER:-stephanos} uv run paper/analysis/benchmark_paper_analysis.py

neural-benchmark-analysis: benchmark-analysis
	cd .. && uv run paper/analysis/neural_benchmark_analysis.py summarize --metrics comet xcomet bleurt

guidance-ablation-analysis:
	cd .. && DB_HOST=$${DB_HOST:-raksasa} DB_USER=$${DB_USER:-stephanos} uv run paper/analysis/guidance_ablation_analysis.py

benchmark-pdf: neural-benchmark-analysis guidance-ablation-analysis
	mkdir -p ../output/pdf
	$(PANDOC) $(BENCHMARK_MD) --from markdown+raw_tex --standalone --resource-path=. --to latex --output $(BENCHMARK_TEX)
	$(XELATEX) -interaction=nonstopmode -halt-on-error -output-directory $(BUILD_DIR) $(BENCHMARK_TEX)
	$(XELATEX) -interaction=nonstopmode -halt-on-error -output-directory $(BUILD_DIR) $(BENCHMARK_TEX)
	$(XELATEX) -interaction=nonstopmode -halt-on-error -output-directory $(BUILD_DIR) $(BENCHMARK_TEX)
	cp $(BUILD_DIR)/benchmark_translation_draft.pdf $(BENCHMARK_PDF)

clean:
	rm -rf $(BUILD_DIR)
