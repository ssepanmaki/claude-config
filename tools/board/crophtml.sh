#!/usr/bin/env bash
# Writes the crop frame page used by slices.sh and zoom.sh (iframe scaled by z, shifted to x,y).
[ -f "$1" ] && exit 0
cat > "$1" <<'EOF'
<!doctype html><meta charset="utf-8"><style>html,body{margin:0;overflow:hidden}iframe{border:0;display:block;transform-origin:0 0}</style>
<script>const q=new URLSearchParams(location.search),z=+(q.get('z')||2);document.write('<iframe src="'+q.get('u')+'" width="'+q.get('w')+'" height="'+q.get('h')+'" style="transform:scale('+z+') translate(-'+q.get('x')+'px,-'+q.get('y')+'px)"></iframe>')</script>
EOF
