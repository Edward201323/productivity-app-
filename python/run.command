#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ ! -d dist/Calendar.app ]]; then
    ./build.command
fi
open dist/Calendar.app
