
IGNORE_LIST := E203,E226,C901

all: clean prep test

clean:
	rm -f *.tmp *.log
	rm -f 1 2 *.1 *.2

prep: black pylama mypy

black:
	black *.py

pylama:
	pylama  --ignore $(IGNORE_LIST) *.py

mypy:
	mypy *.py

test:
	python3 py-read-info.py
