#!/bin/sh
# Same setup and persistent volumes as the CPU launcher, with NVIDIA enabled.
exec sh "$(dirname -- "$0")/avvia.sh" --gpu "$@"
