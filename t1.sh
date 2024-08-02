#! /bin/bash

TEMP_DIR="./tmp"

source .env
mkdir -p ./${TEMP_DIR}/1

find ${TEST_DIR} -type f -print |
grep '.info$' |         # only info files
grep -v '/templates/' | # no template dirs
while read file
do
    grep -q '%}' $file && continue # only files not containing jinja2 macros

    zz=$(
        echo "$file" |
        awk -v path="${TEST_DIR}" '
        {
            rest = substr($0,length(path)+2)
            gsub(/\//, "_", rest)
            print rest
        }
        '
    )

    echo "### $file"
    echo "### $zz"

    python3 ./py_read_info.py $file 2>./${TEMP_DIR}/$zz.2 >./${TEMP_DIR}/$zz.1
    [ -s ./${TEMP_DIR}/$zz.2 ] || {
        rm -f ./${TEMP_DIR}/$zz.2
    }
    [ -s ./${TEMP_DIR}/$zz.1 ] || {
        rm -f ./${TEMP_DIR}/$zz.1
        continue
    }
    mv ./${TEMP_DIR}/$zz.1 ./${TEMP_DIR}/1/

done
