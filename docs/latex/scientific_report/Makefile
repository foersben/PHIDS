# Makefile for PHIDS SIMPAT Scientific Report compilation via latexmk

PROJECT ?= main

.NOTPARALLEL:

all: $(PROJECT).pdf

pdf: $(PROJECT).pdf

$(PROJECT).pdf: $(PROJECT).tex bibliography.bib macros.tex $(wildcard sections/*.tex) $(wildcard tables/*.tex) $(wildcard figures/*.tex) $(wildcard figures/tikz/*.tex) $(wildcard figures/*.pdf)
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PROJECT).tex

clean:
	latexmk -C $(PROJECT).tex 2>/dev/null || true
	rm -f *.aux *.bbl *.blg *.fdb_latexmk *.fls *.log *.out *.toc *.nav *.snm *.synctex.gz

clean-aux:
	latexmk -c $(PROJECT).tex 2>/dev/null || true
	rm -f *.aux *.bbl *.blg *.fdb_latexmk *.fls *.log *.out *.toc *.nav *.snm *.synctex.gz

.PHONY: all pdf clean clean-aux
