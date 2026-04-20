#!/bin/sh
set -eu

if [ ! -d node_modules ] || \
  [ ! -d node_modules/@assistant-ui/react ] || \
  [ ! -d node_modules/react-markdown ] || \
  [ ! -d node_modules/remark-gfm ]; then
  npm install
fi

exec npm run dev
