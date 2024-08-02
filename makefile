# makefile tab=tab
PL_LINTERS	:=	eradicate,mccabe,pycodestyle,pyflakes,pylint
IGNORE_LIST	:=	E203,E226,C901,C0116,C0115,C0114,W0719
LINE_LENGTH	:=	120
TEST_FILE	:=	test.info

all: clean prep test

clean:
	rm -f *.tmp *.log
	rm -f 1 2 *.1 *.2
	rm -rf ./tmp

prep: black pylama mypy

black:
	black \
		--line-length $(LINE_LENGTH) \
		*.py

pylama:
	pylama \
		--max-line-length $(LINE_LENGTH) \
		--linters $(PL_LINTERS) \
		--ignore $(IGNORE_LIST) \
		*.py

mypy:
	mypy \
		--strict \
		--no-incremental \
		*.py

test:py_read_info

py_read_info:
	python3 $@.py $(TEST_FILE) 2>$@.2 | tee $@.1

t1: clean prep
	bash t1.sh
