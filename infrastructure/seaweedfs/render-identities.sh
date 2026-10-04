#!/bin/sh
# Renders the store's identities from the template on stdin to stdout, from the environment.
#
#   S3_ACCESS_KEY, S3_SECRET_KEY                 the admin: dlt, dbt and wwi write with it
#   S3_READER_ACCESS_KEY, S3_READER_SECRET_KEY   optional: a second identity that can only read
#                                                and list S3_BUCKET -- for BI tools and anything
#                                                else that has no business writing to the lake
#
# POSIX sh and sed only: it runs inside the SeaweedFS image, which has busybox and nothing else.
# tests/unit/test_storage_identities.py runs it on the host.
set -eu

: "${S3_ACCESS_KEY:?set S3_ACCESS_KEY}"
: "${S3_SECRET_KEY:?set S3_SECRET_KEY}"

if [ -n "${S3_READER_ACCESS_KEY:-}" ]; then
    : "${S3_READER_SECRET_KEY:?S3_READER_ACCESS_KEY is set, so S3_READER_SECRET_KEY must be too}"
    keep='/^#/d'
else
    # No reader key: drop the whole block rather than render an identity with an empty key.
    keep='/^#reader$/,/^#end-reader$/d'
fi

sed -e "$keep" \
    -e "s|__ACCESS_KEY__|${S3_ACCESS_KEY}|" \
    -e "s|__SECRET_KEY__|${S3_SECRET_KEY}|" \
    -e "s|__READER_ACCESS_KEY__|${S3_READER_ACCESS_KEY:-}|" \
    -e "s|__READER_SECRET_KEY__|${S3_READER_SECRET_KEY:-}|" \
    -e "s|__BUCKET__|${S3_BUCKET:-wwi}|g"
