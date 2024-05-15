#!/usr/bin/env bash

# Global variables
export JARVICE_SCHED_LOGLEVEL="10"
export JARVICE_SYSTEM_REGISTRY="us-docker.pkg.dev"
export JARVICE_SYSTEM_REPO_BASE="jarvice-system/images"
export JARVICE_IMAGES_TAG="jarvice-master"
export JARVICE_BAREMETAL_EXECUTOR="singularity"

# the following variables must be set to base64 values provided by Eviden;
# please contact Eviden if you are a developer and wish to test end-to-end
# with a JARVICE upstream
export JARVICE_DOCKER_USERNAME=""
export JARVICE_DOCKER_PASSWORD=""

# Singularity variables
export JARVICE_SINGULARITY_OVERLAY_SIZE="600"
export JARVICE_SINGULARITY_VERBOSE="true"

# Slurm variables
# replace with appropriate values for your cluster if you intend to test
# the Slurm-via-SSH example
export JARVICE_SLURM_CLUSTER_ADDR="<address>"
export JARVICE_SLURM_CLUSTER_PORT="22"
export JARVICE_SLURM_SSH_USER="<username>"
export JARVICE_SLURM_SSH_PKEY="<SSH-private-key>"

python3 main.py
