#! /bin/bash

source .env
mkdir -p ./tmp

find ${TEST_DIR} -type f -print |
grep '.info$' |         # only info files
grep -v '/templates/' | # no template dirs
while read file
do
    grep -q '%}' $file && continue # only files not containing jinja2 macros

    zz=$(
        echo "$file" |
        awk '
        {
            sub(/.*\/RevLabs\/github.rl.lan\/mboot\/titanium_core\//, "", $0)
            gsub(/\//, "_", $0)
            print
        }
        '
    )

    echo "### $file"
    echo "### $zz"

    python3 ./py_read_info.py $file 2>./tmp/$zz.2 >./tmp/$zz.1
    [ -s ./tmp/$zz.2 ] || {
        rm -f ./tmp/$zz.2
    }
    [ -s ./tmp/$zz.1 ] || {
        rm -f ./tmp/$zz.1
    }

done
