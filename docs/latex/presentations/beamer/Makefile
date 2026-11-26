# Makefile for LaTeX Beamer Presentation with Dual Compilation

LATEX = pdflatex -interaction=nonstopmode
FILE = presentation

all: $(FILE).pdf $(FILE)_notes.pdf

$(FILE).pdf: $(FILE).tex
	$(LATEX) $(FILE).tex
	# Run twice to resolve references/pagination
	$(LATEX) $(FILE).tex

$(FILE)_notes.pdf: $(FILE).tex
	# Automatically swap the setbeameroption for the notes version
	sed 's/\\setbeameroption{hide notes}/\\setbeameroption{show only notes}/' $(FILE).tex > $(FILE)_notes.tex
	$(LATEX) $(FILE)_notes.tex
	$(LATEX) $(FILE)_notes.tex

clean:
	rm -f *.aux *.log *.nav *.out *.snm *.toc *.synctex.gz *.fdb_latexmk *.fls *.vrb *_notes.tex

clean-all: clean
	rm -f $(FILE).pdf $(FILE)_notes.pdf

.PHONY: all clean clean-all
