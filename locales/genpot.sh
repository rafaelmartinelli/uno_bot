#!/usr/bin/env bash

set -euo pipefail

current_ver='1.0'
project_root="$(cd "$(dirname "$0")/.." && pwd)"

find "$project_root/unobot" -name '*.py' -print0 | xargs -0 xgettext \
  --output "$project_root/locales/unobot.pot" \
  --foreign-user \
  --package-name "uno_bot" \
  --package-version "$current_ver" \
  --msgid-bugs-address 'uno@jhoeke.de' \
  --keyword=__ \
  --keyword=_ \
  --keyword=_:1,2 \
  --keyword=__:1,2
