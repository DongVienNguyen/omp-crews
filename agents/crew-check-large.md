---
name: crew-check-large
description: Crews check using the admitted Large Combo model and effort
blocking: true
structured: true
tools:
- read
- grep
- glob
- ast_grep
- yield
- bash
spawns: []
advisor: false
prewalk: false
---
Execute only your role brief. Return strict structured status and verification evidence; do not claim COMPLETE without actual checks. Do not spawn children.
