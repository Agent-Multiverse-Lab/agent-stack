#!/bin/sh
set -eu
# The official init validates/prepares directories. Disk/kernel installation stays disabled.
/scripts/cube-node-init.sh
# Write through the dedicated writable state mount; /host remains read-only.
HOST_ROOT=""
. /scripts/node-prep-lib.sh
write_node_prep_ready
