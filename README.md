```
     ██  █████  ██████  ██    ██ ██  ██████ ███████     ██████  ███████ ███████ ██████  
     ██ ██   ██ ██   ██ ██    ██ ██ ██      ██          ██   ██ ██      ██      ██   ██ 
     ██ ███████ ██████  ██    ██ ██ ██      █████       ██   ██ ███████ ███████ ██████  
██   ██ ██   ██ ██   ██  ██  ██  ██ ██      ██          ██   ██      ██      ██ ██   ██ 
 █████  ██   ██ ██   ██   ████   ██  ██████ ███████     ██████  ███████ ███████ ██   ██ 
                                                                                        
    Stands for Downstream Slurm Scheduler Refactoring or something like that ;)
```

# Jarvice DSSR

## Introduction

The Jarvice DSSR aims to be a simple downstream scheduler for Jarvice.
It acts as an interface between Jarvice upstream and the bare metal HPC scheduler.

## Requirements

This server can run on any kind of system, even Microsoft Windows.

Needed pip3 dependencies:

```
pip3 install json waitress flask paramiko
```

Some useful resources for developers:

https://flask.palletsprojects.com/en/3.0.x/
https://flask.palletsprojects.com/en/3.0.x/deploying/waitress/
https://www.paramiko.org/

## Architecture

```
           Jarvice Upstream                         Shell Script                
                                                 or manual usage                
                   │                                                            
                   │                                     │                      
                   │                                     │                      
                   │                                     │                      
                   ├─────────────────────────────────────┘                      
                   │
                   │
                   │
                   │
                   ▼
(1)     ┌─────────────────────┐
        │Legacy API           │
        │                     │
        │                     │
        │                     │
        │                     │
        └──────────┬──────────┘
                   │           
                   │           
                   └───────────┐
                               │
                               │
                               ▼
(4)                ┌───────────────────────────────────────┐                    
                   │      Main                             │                    
                   │                                       │                    
                   │ Flask http endpoints                  │                    
                   │                                       │                    
                   └──────────────────┬────────────────────┘                    
                                      │                                         
                                      │                                         
                   ┌──────────────────┘
                   │
                   │
                   ▼
(2)       ┌──────────────────┐
          │Slurm baremetal   │
          │    connector     │
          │                  │
          └────────┬─────────┘
                   │
                   │
               ssh │
                   │
                   ▼
        ┌─────────────────────┐
        │ Bare metal slurm    │
(3)     │    Singularity      │
        │                     │
        └─────────────────────┘
```

### API from upstream

The DSSR scheduler uses legacy API (1), which is defined inside the main file (4).
The code can easily be upgraded to support both legacy and a new RestFull API using Flask Restfull.

### Bare metal connector

Bare metal connector acts as a layer between the core and the bare metal scheduler running on the bare metal HPC cluster.
Only a single connector can be used at a time. The current Slurm connector can simply be replaced by another file to match another kind of bare metal scheduler and to use another method to dialogate with it (could be HTTP API based for example).

### Executor

It is possible to select a specific executor to run apps on the target cluster. (3)

For now, only singularity is supported.

This is set by the `JARVICE_BAREMETAL_EXECUTOR` environment variable.

The following parameters are available for the singularity executor:

* `JARVICE_SINGULARITY_OVERLAY_SIZE`: default `600`. Define size on Mb of the overlay image during runtime.
* `JARVICE_SINGULARITY_VERBOSE`: default `false`. If set to `true`, this will enable verbose mode on sigularity calls.

## Slurm connector

The Slurm connector encapsulate the script provided by core by adding `srun` command, and also adding dynamic Slurm's environment mapping the the script.

It uses ssh to connect to target cluster.

The following parameters are needed as environment variables to ensure proper connection to target cluster:

* `JARVICE_SLURM_CLUSTER_ADDR`: ipv4 of the target slurm cluster
* `JARVICE_SLURM_CLUSTER_PORT`: port to be used as ssh entry point for the target slurm cluster
* `JARVICE_SLURM_SSH_USER`: user to be used to login to target cluster
* `JARVICE_SLURM_SSH_PKEY`: private key (prefered ed25519) to connect to target cluster

Note that `JARVICE_SLURM_SSH_PKEY` can be provided base64 encoded and decoded, to prevent any launch issues. Example:

```
export JARVICE_SLURM_SSH_PKEY=$(echo "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUJsd0FBQUFkemMyZ3RjbgpOaEFBQUFBd0VBQVFBQUFZRUF3ZXJralpPcnBHRqQnZIeksycmhHbjAKa0V4emo3WFNsejMvQ1ZSbStyT2lySmhNZDY2VnJKdTg0c3IvN25YdkN2Nno1QnlqY3o4dHVBVE0xRHhuaVVBS0RkUm9zYQplMG5sMFZSTzl4TEQ5VkE0U2NqWnhSUmFzZmJWOHpNanNBQUFEQkFNd09kbUhiYnBkUkk2S25JVVN1OHo1Q1p5Z0xEelBICkRBeUdxSGdKZWZLdFJkZ2dTKzRmV1pLMHlHTSt3UXBDS2RWRzZ6S295MEFibmRBWDNrMkpRaWUxYkZyYnAyRkpjN1ZkVGsKUGtIelIwY1QvdUhDZnc5MUpjYmFTd2YyNGt4VEFoR29nTUsranFVVGxHSVF3MVZrR0dIQW9sSHZycWtzK05Ea2lta0kyTwpSV1RlSko1cEgrZGNjODd1Njdiek5iVDkzWXR3bFpFaEdROFNNMklIbXdpcWg5UXJkSTBXeGQ2T0xPTEdIOTdsa09ybUJjCkNoVFZMZ0xXZkZZNUJCZVFBQUFCQnFZWEoyYVdObFFHOTRMV3h2WjJsdUFRPT0KLS0tLS1FTkQgT1BFTlNTSCBQUklWQVRFIEtFWS0tLS0tCg==" | base64 -d)
```
