#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ ! -d "dist/lock in no gooning.app" ]]; then
    ./build.command
fi
open "dist/lock in no gooning.app"
