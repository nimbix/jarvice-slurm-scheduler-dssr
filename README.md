```
     ██  █████  ██████  ██    ██ ██  ██████ ███████     ██████  ███████ ███████ ██████  
     ██ ██   ██ ██   ██ ██    ██ ██ ██      ██          ██   ██ ██      ██      ██   ██ 
     ██ ███████ ██████  ██    ██ ██ ██      █████       ██   ██ ███████ ███████ ██████  
██   ██ ██   ██ ██   ██  ██  ██  ██ ██      ██          ██   ██      ██      ██ ██   ██ 
 █████  ██   ██ ██   ██   ████   ██  ██████ ███████     ██████  ███████ ███████ ██   ██ 
                                                                                        
    Stands for Downstream Scheduler Simplification and Refactoring (or something like that...)
```

## 1. Introduction

The Jarvice DSSR aims to be a simple downstream scheduler for Jarvice.
It acts as an interface between Jarvice upstream and any other kind of job scheduler.

## 2. Requirements

This service can run on any kind of system, even Microsoft Windows, as long as a recent Python 3 is setup.
It was developed on Debian 12 with Python 3.11.2.

Needed pip3 dependencies (recommended to work in a Python virtual environment):

```
pip3 install pyjson waitress flask paramiko pyyaml PyJWT
```

**json** and **yaml** are standard, **waitress** and **flask** are used for the http front end, **paramiko** to manage ssh layer between this downstream and the target cluster (optional), and **PyJWT** to decode bearer tokens sent by Jarvice upstream at job submission (optional).

Some useful resources for developers:

* https://flask.palletsprojects.com/en/3.0.x/
* https://flask.palletsprojects.com/en/3.0.x/deploying/waitress/
* https://www.paramiko.org/

## 3. Architecture

```
           Jarvice Upstream                         Shell Script                
                                                 or manual usage (API direct call)               
                   │                                                            
                   │                                     │                      
                   │                                     │                      
                   │                                     │                      
                   ├─────────────────────────────────────┘                      
                   │
                   │
              http │
                   │
                   ▼
(1)     ┌─────────────────────┐
        │    Legacy API       │
        │                     │
        └──────────┬──────────┘      
(2)     ┌───────────────────────────────────────┐                    
        │      Main                             │                    
        │                                       │                    
        │ Flask http endpoints                  │                    
        │                                       │                    
        └──────────┬────────────────────────────┘                    
(3)     ┌─────────────────────┐
        │    connector        │
        │                     │
        └──────────┬──────────┘
                   │
                   │
               ssh │ (but could be something else depending of the connector selected)
                   │
                   ▼
        ┌─────────────────────┐
        │ local jobs executor │
(4)     │                     │
        │                     │
        └─────────────────────┘
```

### 3.1. API from upstream

The DSSR scheduler uses Jarvice legacy API (1), which is defined inside the main file (2).
The code can easily be upgraded to support both legacy and a new RestFull API using Flask Restfull.

### 3.2. Connector

The connector (3) acts as a layer between the core and the local job scheduler/executor (which could be Slurm for bare metal, or any other kind of tool).
Only a single connector can be used at a time. The current default Slurm connector can simply be replaced by another file to match another kind of local scheduler and to use another method to dialogate with it (could be HTTP API based for example).

To specify connector to be used, set `JARVICE_BAREMETAL_CONNECTOR` environment variable.

For example, to use the slurm connector:

```
export JARVICE_BAREMETAL_CONNECTOR="connectors.slurm.connector"
```

Note: importlib expect a dot `.` in place of `/` for folders. Since the slurm connector file is located at relative path `connectors/slurm/connector.py`, the final string to pass is `connectors.slurm.connector`.

Each connector posses its own README file:

* [Slurm README](connectors/slurm/README.md)
* [Dummy README](connectors/dummy/README.md)

### 3.3. Executor

It is possible to select a specific executor to run apps on the target cluster. (4)

During submition process, the data sent by upstream contains some proposals of script to be parsed and used inside local job scheduler, as executors.
For example, for the Slurm connector, the singularity script provided by upstream is used as executor.

For now, only Singularity is proposed.

This is set by the `JARVICE_BAREMETAL_EXECUTOR` environment variable.

For example, to use the Slurm connector with the Singularity executor, variables would be:

```
export JARVICE_BAREMETAL_CONNECTOR="connectors.slurm.connector"
export JARVICE_BAREMETAL_EXECUTOR="singularity"
```

#### 3.3.1. Singularity executor

The following parameters are available for the singularity executor, as environment variable:

* `JARVICE_SINGULARITY_OVERLAY_SIZE`: default `600`. Define size on Mb of the overlay image during runtime. Setting this value to `0` push the tool to try to fallback on writable tmpfs instead of overlayfs. Writable tmpfs can leads to compatibility issues with some apps.
* `JARVICE_SINGULARITY_VERBOSE`: default `false`. If set to `true`, this will enable verbose mode on sigularity calls.

To use this executor with a new connector, you need to:

1. Inject your local downstream values, using a connection script, and injecting it inside the script sent by upstream, replacing the variable `DOWNSTREAM_PARAMETERS`.

For example, the Slurm connector uses this script:

```
# --------------------------------------------------------------------------
# Main parameters from baremetal Dowstream
# This part is dynamic
# and can be adapted to any kind of bare metal job scheduler
# See this section as a "connector"

# Global parameters
export JARVICE_JOB_SCRATCH_DIR={JARVICE_JOB_SCRATCH_DIR}
export JARVICE_JOB_GLOBAL_SCRATCH_DIR={JARVICE_JOB_GLOBAL_SCRATCH_DIR}
export JARVICE_JOB_APP_IS_IN_GLOBAL_REGISTRIES="{JARVICE_JOB_APP_IS_IN_GLOBAL_REGISTRIES}"
export SINGULARITYENV_JARVICE_SERVICE_PORT={JARVICE_SERVICE_PORT}
export SINGULARITYENV_JARVICE_SSH_PORT={JARVICE_SSH_PORT}
export JARVICE_SINGULARITY_TMPDIR={JARVICE_SINGULARITY_TMPDIR}

# User
export JOB_LOCAL_USER=$USER

# Singularity and images parameters
export JARVICE_SINGULARITY_OVERLAY_SIZE={JARVICE_SINGULARITY_OVERLAY_SIZE}

# Possible credentials
export JARVICE_INIT_DOCKER_USERNAME="{JARVICE_INIT_DOCKER_USERNAME}"
export JARVICE_INIT_DOCKER_PASSWORD="{JARVICE_INIT_DOCKER_PASSWORD}"
export JARVICE_DOCKER_USERNAME="{JARVICE_DOCKER_USERNAME}"
export JARVICE_DOCKER_PASSWORD="{JARVICE_DOCKER_PASSWORD}"

# Images
export JARVICE_APP_IMAGE={JARVICE_APP_IMAGE}
export JARVICE_INIT_IMAGE={JARVICE_INIT_IMAGE}

# Final CMD from downstream
export JARVICE_CMD={JARVICE_CMD}

# Enable or not verbosity in steps
export SV_FLAG="-s"
export SV={SINGULARITY_VERBOSE}
[ "$SV" = "true" ] && export SV_FLAG="-v"

# Proxy parameters
export SCHTTP_PROXY={JARVICE_BAREMETAL_HTTP_PROXY}
export SCHTTPS_PROXY={JARVICE_BAREMETAL_HTTPS_PROXY}
export SCNO_PROXY={JARVICE_BAREMETAL_NO_PROXY}

# --------------------------------------------------------------------------
```

2. Make the script compatible with your local scheduler. For example, the Slurm connector is adding the following content on top of the script, to make it compatible with Slurm execution:

```
# --------------------------------------------------------------------------
# Dynamic/binding parameters, to connect to job scheduler
export PROCESS_PROCID=$SLURM_PROCID
export PROCESS_NODENAME=$SLURMD_NODENAME
export JOB_JOBID=$SLURM_JOBID
export JOB_JOB_NODELIST=$SLURM_JOB_NODELIST
export JOB_JOB_FORMATED_NODELIST=$(scontrol show hostname $JOB_JOB_NODELIST | sed ":b;N;$!bb;s/\\n/ /g")
export JOB_NNODES=$SLURM_NNODES
export JOB_NTASKS=$SLURM_NTASKS
export JOB_SUBMIT_DIR=$SLURM_SUBMIT_DIR
export JOB_GPUS_PER_NODE=$SLURM_GPUS_PER_NODE
# --------------------------------------------------------------------------
```

And is also wrapping the whole content with an srun execution.

During the script execution, the folder `$JARVICE_JOB_SCRATCH_DIR.jarvice/jobs/$JOB_JOBID` will be created, and mutltiple subfolders too.
The Jarvice init image will be pulled, and some libs and bins will be extracted from it to allow execution.

## 4. Examples

### 4.1. Slurm with Singularity

Create the following launch script, self explained via comments:

```
#!/usr/bin/env bash

# Global
export JARVICE_SCHED_LOGLEVEL="10"
  # Init image from Jarvice
export JARVICE_SYSTEM_REGISTRY="us-docker.pkg.dev"                    # Registry from which to grab Jarvice init images
export JARVICE_SYSTEM_REPO_BASE="jarvice-system/images"               # Repository from which to grab Jarvice init images
export JARVICE_IMAGES_TAG="jarvice-3.24.5"                            # Tag of init images to grab
  # Jarvice repository credentials.
  # If using a json based key, set JARVICE_DOCKER_USERNAME to X2pzb25fa2V5 ("_json_key" -> base64)
  # and set JARVICE_DOCKER_PASSWORD as the base64 encoded json file
  # If using user/password, use base64 encoded user/password
export JARVICE_DOCKER_USERNAME="<username> base64 encoded"                         
export JARVICE_DOCKER_PASSWORD="<password/jsonkey> base64 encoded"

# Connector
export JARVICE_BAREMETAL_CONNECTOR="connectors.slurm.connector"

# Executor
export JARVICE_BAREMETAL_EXECUTOR="singularity"
  # Singularity variables
export JARVICE_SINGULARITY_OVERLAY_SIZE="600"
export JARVICE_SINGULARITY_VERBOSE="true"

# Slurm variables
export JARVICE_SLURM_CLUSTER_ADDR="<address>"
export JARVICE_SLURM_CLUSTER_PORT="22"
export JARVICE_SLURM_SSH_USER="<username>"
export JARVICE_SLURM_SSH_PKEY="<SSH-private-key>"

python3 main.py
```

Then make it executable and launch it.
