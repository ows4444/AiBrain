---
title: Tuning
type: tuning
---

# Tuning

The thresholds this brain holds at another value than the engine's default,
one line each under the heading below: `- name = value (why, and when)`.
`brain introspect --usage` lists every threshold with its default, its range
and what it does. Measure a value before keeping it: `brain eval --set
name=value` runs the question set with it and writes nothing. `brain check`
fails on a name that is not a threshold or a value outside its range. To go
back to the default, remove the line.

## Overrides
