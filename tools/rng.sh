#!/usr/bin/env bash
# rng.sh [-w cols] file:a-b [file:a-b ...]  -> numbered line ranges, one header per range (replaces chained sed -n | cut)
w=240
[ "$1" = -w ] && { w=$2; shift 2; }
for spec in "$@"; do
  f=${spec%:*}; r=${spec##*:}
  [ "$f" = "$spec" ] && r=1-80
  a=${r%-*}; b=${r#*-}
  echo "== $f:$a-$b"
  sed -n "${a},${b}p" "$f" | awk -v s="$a" -v w="$w" '{print s+NR-1 "\t" substr($0,1,w)}'
done
