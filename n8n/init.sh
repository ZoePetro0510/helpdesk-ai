#!/bin/sh
# Import the version-controlled workflows and activate them, then start n8n.
# Re-importing on every start keeps n8n in sync with the files in n8n/workflows.
set -e
n8n import:workflow --separate --input=/workflows
n8n update:workflow --all --active=true
exec n8n start
