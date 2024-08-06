# py-read-info
read info type config files

## WORK IN PROGRESS

the tokenizer works, itterpreter comes next
data will be stored in nested dicts unless we have fully duplicate keys then keys/values will be arrays

## INFO files

info files are described in
[info_parser](https://www.boost.org/doc/libs/1_85_0/doc/html/property_tree/parsers.html#property_tree.parsers.info_parser)
and look similar to config files used in nginx and dovecot.


## Stream preparation

While reading the token stream we apply corrections:

 - Remove comments starting with `;`; if a ; needs to be in a word if must be inside a string.
 - Allways a newline after BLOCK_START `{`; if there is no newline it will be added.
 - NO newline before a BLOCK_START `{`; if it is there it will be removed from the token stream.
 - look for STRING \\ newline STRING and combine the 2 strings info one.
    Will allow for multiple continuation lines.
 - A newline before and after a BLOCK_CLOSE `}`.

As a result of the corrections blocks will always be seen as:


    key value {
        "block content"
    }
    ; or
    key {
        "block content"
    }

This significantly eases the parsing of lines as we now have only 5 distinct line types:

 1. `key` newline.
 1. `key` `value` newline.
 1. `key` `{` newline.
 1. `key` `value` `{` newline.
 1. } newline.

Possily in a future iteration this could be used to create a linter/reformatter, preserving comments.


According to the original implementation of the info files,
blocks are stored under the `key` with optional `value` and keys are not unique but stored in a list.

Using python `Dicts` of
`data[key][value] -> block`
we make the process more efficient.

In leaf nodes multiple values are stored as array if duplicates are detected.

    key1 value1
    key1 value2

will be stored as `data[key1] -> [value1, value2]`
