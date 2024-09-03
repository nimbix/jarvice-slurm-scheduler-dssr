```
     ██  █████  ██████  ██    ██ ██  ██████ ███████     ██████  ███████ ███████ ██████  
     ██ ██   ██ ██   ██ ██    ██ ██ ██      ██          ██   ██ ██      ██      ██   ██ 
     ██ ███████ ██████  ██    ██ ██ ██      █████       ██   ██ ███████ ███████ ██████  
██   ██ ██   ██ ██   ██  ██  ██  ██ ██      ██          ██   ██      ██      ██ ██   ██ 
 █████  ██   ██ ██   ██   ████   ██  ██████ ███████     ██████  ███████ ███████ ██   ██ 
                                                                                        
    Stands for Downstream Slurm Scheduler Refactoring or something like that ;)
```

## Introduction

The Jarvice DSSR aims to be a simple downstream scheduler for Jarvice.
It acts as an interface between Jarvice upstream and the bare metal HPC scheduler.

Kubernetes pods management natively used in Jarvice is replaced here by usage of Singularity, but could be any other similar baremetal tool.

## Requirements

This service can run on any kind of system, even Microsoft Windows, as long as a recent Python 3 is setup.
It was developed on Debian 12 with Python 3.11.2.

Needed pip3 dependencies (recommended to work in a Python virtual environment):

```
pip3 install json waitress flask paramiko yaml PyJWT
```

**json** and **yaml** are standard, **waitress** and **flask** are used for the http front end, **paramiko** to manage ssh layer between this downstream and the target cluster, and **PyJWT** to decode bearer tokens sent by Jarvice upstream at job submission.

Some useful resources for developers:

* https://flask.palletsprojects.com/en/3.0.x/
* https://flask.palletsprojects.com/en/3.0.x/deploying/waitress/
* https://www.paramiko.org/

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
              http │
                   │
                   ▼
(1)     ┌─────────────────────┐
        │    Legacy API       │
        │                     │
        └──────────┬──────────┘      
(4)     ┌───────────────────────────────────────┐                    
        │      Main                             │                    
        │                                       │                    
        │ Flask http endpoints                  │                    
        │                                       │                    
        └──────────────────┬────────────────────┘                    
(2)               ┌──────────────────┐
                  │   Baremetal      │
                  │    connector     │
                  │                  │
                  └────────┬─────────┘
                   ┌───────┘
                   │
                   │
               ssh │
                   │
                   ▼
        ┌─────────────────────┐
        │ Baremetal  executor │
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

To specify connector to be used, set `JARVICE_BAREMETAL_CONNECTOR` environment variable.

For example, to use the slurm connector:

```
export JARVICE_BAREMETAL_CONNECTOR="slurm"
```

### Bare metal executor

It is possible to select a specific executor to run apps on the target cluster. (3)

For now, only Singularity is supported.

This is set by the `JARVICE_BAREMETAL_EXECUTOR` environment variable.

For example, to use the slurm connector:

```
export JARVICE_BAREMETAL_EXECUTOR="singularity"
```

## Executors

### Singularity executor

The following parameters are available for the singularity executor, as environment variable:

* `JARVICE_SINGULARITY_OVERLAY_SIZE`: default `600`. Define size on Mb of the overlay image during runtime. Setting this value to `0` push the tool to try to fallback on writable tmpfs instead of overlayfs. Writable tmpfs can leads to compatibility issues with some apps.
* `JARVICE_SINGULARITY_VERBOSE`: default `false`. If set to `true`, this will enable verbose mode on sigularity calls.

## Connectors

### Slurm connector

The Slurm connector is for now the default one. It is able to submit jobs to a bare metal slurm cluster, using both CLI and REST HTTP interfaces of Slurm.

#### Slurm cluster setup

Some specific preparation must be made on Slurm cluster to be able to use it via Jarvice JXE.

##### The Jarvice user

A specific user must be created on the target cluster. Default name is `jarvice`. This user acts as the ssh entry point to the cluster, and will be used to manage jobs (submitting, releasing, terminating, grabbing logs, etc.).

The user MUST have the same uid on the whole cluster, and so should be configured like any other traditional unpriviledged users (LDAP, etc).

This user is set later using the `JARVICE_SLURM_SSH_USER` environment variable.

##### SSH keys to connect to the cluster

Once user has been created, an ssh key couple is needed. Generate a new key pair, without passphrase:

```
ssh-keygen -t ed25519 -f ./jarvice_id_ed25519 -q -N ""
```

Grab `jarvice_id_ed25519` content, this will be needed as `JARVICE_SLURM_SSH_PKEY` environment variable, coupled to the previsouly seen `JARVICE_SLURM_SSH_USER`.

Then grab `jarvice_id_ed25519.pub` content, and add it to authorized_keys of the Jarvice user on the slurm cluster.

##### Accounts coordinator

The Jarvice user `jarvice` must be set **coordinator** of every accounts that contains users using Jarvice portal. This allows the Jarvice user to see associated accounts jobs (even if `PrivateData` key is set in slurm.conf), and release or terminate them.

Assuming the slurmdbd daemon is running and properly configured, and that a slurm cluster has been created on the target cluster, here is the procedure to create accounts, add users to accounts, and set Jarvice user as coordinator of these accounts. Please adapt to your needs:

```
sacctmgr add cluster valhalla # Create valhalla cluster
sacctmgr add account nintendo cluster=valhalla # Create nintendo account
sacctmgr add account pc cluster=valhalla
sacctmgr add user names=kirby,mario account=nintendo cluster=valhalla # Add users kirby and mario to nintendo account
sacctmgr add user names=dovahkiin account=pc cluster=valhalla
sacctmgr add coordinator account=nintendo names=jarvice cluster=valhalla # Make jarvice user a coordinator of nintendo account
sacctmgr add coordinator account=pc names=jarvice cluster=valhalla
```

Now jarvice user is able to see jobs of all associated accounts users, so in this example, kirby, mario and dovahkiin.

Please refer to Slurm documentation for details or more complex setups.

##### Scratch structure

A dedicated scratch must be setup for:

1. Images cache (shareds and privates)
2. Images pull locks (shareds and privates)
3. Jobs temporary files (private)
4. Jobs logs storage (private)

While each user must be contained in its own directory in the Jarvice dedicated scratch, the `jarvice` user must be able to read/write in all users' jarvice scratch.
This mechanism requires usage of Linux groups (gid) or file system ACLs. To be defined depending of target cluster shared FS.

We will assume here that jarvice dedicated scratch path is `/jxe_scratch`, and that this directory is mounted on all `slurmd` workers, and on the node where `jarvice` user is operating (where downstream ssh into to operate, mostly login nodes). We also assume the file system is compatible with Linux groups or with POSIX ACLs.

Note: we will assume here a basic configuration. It is possible to further improve security, for example using a dedicated group for all users using Jarvice to submit jobs, etc.

Make `jarvice` user owner of this directory and the internal:

```
mkdir /jxe_scratch
mkdir /jxe_scratch/images
mkdir /jxe_scratch/cache
mkdir /jxe_scratch/users
chown -R jarvice:jarvice /jxe_scratch
```

Then allow users to open these directories, and write into images and cache:

```
chmod 755 /jxe_scratch
chmod 777 /jxe_scratch/images
chmod 777 /jxe_scratch/cache
chmod 755 /jxe_scratch/users
```

Now, for each user of Jarvice, create a dedicated folder under users, and make this user proprietary of it, so no other users can read/write into it:

```
mkdir /jxe_scratch/users/kirby
chown -R kirby:kirby /jxe_scratch/users/kirby
chmod -R 770 /jxe_scratch/users/kirby
```

Last step is to make `jarvice` user able to read and write also in to this user dedicated jarvice scratch.

If using groups, simply add `jarvice` user to `kirby` group:

```
usermod -a -G kirby jarvice
```

If using ACL, use `setfacl` command. It is important to note that we configure it as default ACL, so that this ACL is propagated to any newly created subfolder and files later.

```
setfacl -m jarvice:rwx /jxe_scratch/users/kirby
setfacl -m default:jarvice:rwx /jxe_scratch/users/kirby
```

You can check using getfacl command on the directory:

```
# file: jxe_scratch/users/kirby
# owner: kirby
# group: kirby
user::rwx
user:jarvice:rwx
group::rwx
mask::rwx
other::---
default:user::rwx
default:user:jarvice:rwx
default:group::rwx
default:mask::rwx
default:other::---
```

Important note about ACLs: while NFSv3 supports POSIX ACL, NFSv4 introduces a new type of ACLs and so should be managed differently. Please refer to NFS documentation.

Repeat this for each users so that each Jarvice user posses her/his own Jarvice scratch folder, also read/writable by `jarvice` user.
The `/jxe_scratch` directory will have to be set later as `JARVICE_BAREMETAL_SCRATCH_DIR` environment variable of the downstream scheduler.

#### Downstream configuration

Now that everything is configured on the slurm bare metal cluster, and that the `jarvice` user is created along with all the requirements, some settings are required for the slurm connector.

The Slurm connector encapsulate the script provided by upstream by adding `srun` command, and also adding dynamic Slurm's environment mapping the the script.

It uses ssh to connect to target cluster, and submit jobs via 2 methods:

1. Using CLI sbatch. If using this method, the slurm connector will rely on users id mapping (see bellow) to directly ssh to users accounts and submit jobs from there.
2. Using slurmrestd HTTP POST request. If using this method, the slurm connector will not use id mapping, but use the jarvice user to submit jobs using the bearer token received from upstream.

User can define method to be used by setting `JARVICE_SLURM_INTERFACE` environment variable to either `cli` either `http`.

The following parameters are needed as environment variables to ensure proper connection to target cluster:

* `JARVICE_SLURM_CLUSTER_ADDR`: ipv4 of the target slurm cluster
* `JARVICE_SLURM_CLUSTER_PORT`: port to be used as ssh entry point for the target slurm cluster
* `JARVICE_SLURM_SSH_USER`: user to be used to login to target cluster
* `JARVICE_SLURM_SSH_PKEY`: private key (prefered ed25519) to connect to target cluster

Note that `JARVICE_SLURM_SSH_PKEY` can be provided base64 encoded and decoded on the fly to prevent any launch issues. Example:

```
export JARVICE_SLURM_SSH_PKEY=$(echo "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUJsd0FBQUFkemMyZ3RjbgpOaEFBQUFBd0VBQVFBQUFZRUF3ZXJralpPcnBHRqQnZIeksycmhHbjAKa0V4emo3WFNsejMvQ1ZSbStyT2lySmhNZDY2VnJKdTg0c3IvN25YdkN2Nno1QnlqY3o4dHVBVE0xRHhuaVVBS0RkUm9zYQplMG5sMFZSTzl4TEQ5VkE0U2NqWnhSUmFzZmJWOHpNanNBQUFEQkFNd09kbUhiYnBkUkk2S25JVVN1OHo1Q1p5Z0xEelBICkRBeUdxSGdKZWZLdFJkZ2dTKzRmV1pLMHlHTSt3UXBDS2RWRzZ6S295MEFibmRBWDNrMkpRaWUxYkZyYnAyRkpjN1ZkVGsKUGtIelIwY1QvdUhDZnc5MUpjYmFTd2YyNGt4VEFoR29nTUsranFVVGxHSVF3MVZrR0dIQW9sSHZycWtzK05Ea2lta0kyTwpSV1RlSko1cEgrZGNjODd1Njdiek5iVDkzWXR3bFpFaEdROFNNMklIbXdpcWg5UXJkSTBXeGQ2T0xPTEdIOTdsa09ybUJjXXXXXXXX==" | base64 -d)
```

If using experimental Slurm REST API support, the following environment variables are also needed:

* `JARVICE_SLURMRESTD_API_VERSION`: API version to use. Devs were made on "v0.0.40".
* `JARVICE_SLURMRESTD_ADDR`: slurmrestd hostname, including http:// string, so for example "http://mg1".
* `JARVICE_SLURMRESTD_PORT`: slurmrestd port, default is "6820".

In order to allow the downstream to pull images (init images) from Jarvice official registry, or from a local air gapped registry, some docker credentials have to be provided, and set using associated variables:

* `JARVICE_DOCKER_USERNAME`: Jarvice registry username, base64 encoded
* `JARVICE_DOCKER_PASSWORD`: Jarvice registry password, base64 encoded

These variables must be set to base64 values provided by Eviden; please contact Eviden if you are a developer and wish to test end-to-end with a JARVICE upstream.

Last part is to define Jarvice registry to pull init images from, associated repo, and images tag to comply with an upstream version if needed.

* `JARVICE_SYSTEM_REGISTRY`: Registry hostname, for example "us-docker.pkg.dev"
* `JARVICE_SYSTEM_REPO_BASE`: Repo name on registry, for example "jarvice-system/images"
* `JARVICE_IMAGES_TAG`: Image tag on repo, for example "jarvice-master"

An example of local starting script can be:

```bash
#!/usr/bin/env bash

export JARVICE_SCHED_LOGLEVEL="10"

export JARVICE_SYSTEM_REGISTRY="us-docker.pkg.dev"
export JARVICE_SYSTEM_REPO_BASE="jarvice-system/images"
export JARVICE_IMAGES_TAG="jarvice-master"

# the following variables must be set to base64 values provided by Eviden;
# please contact Eviden if you are a developer and wish to test end-to-end
# with a JARVICE upstream
export JARVICE_DOCKER_USERNAME="X2pzb25fa2V5"
export JARVICE_DOCKER_PASSWORD="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

# Executor - Singularity variables
export JARVICE_BAREMETAL_EXECUTOR="singularity"
export JARVICE_SINGULARITY_OVERLAY_SIZE="600"
export JARVICE_SINGULARITY_VERBOSE="true"

# Connector - Slurm variables
# replace with appropriate values for your cluster if you intend to test
# the Slurm-via-SSH example

export JARVICE_BAREMETAL_CONNECTOR="slurm"
export JARVICE_SLURM_INTERFACE="cli"
export JARVICE_SLURM_CLUSTER_ADDR="<address>"
export JARVICE_SLURM_CLUSTER_PORT="22"
export JARVICE_SLURM_SSH_USER=$(echo amFydmljZQ== | base64 -d)
export JARVICE_SLURM_SSH_PKEY=$(echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX | base64 -d)

# If using slurmrestd
# export JARVICE_SLURMRESTD_API_VERSION="v0.0.40"
# export JARVICE_SLURMRESTD_ADDR="http://mg1"
# export JARVICE_SLURMRESTD_PORT="6820"

python3 main.py
```

Please adapt this to your target system (could be bare metal script, systemd, K8S pod, etc.).

#### Users ID mapping

If `JARVICE_SLURM_INTERFACE="cli"`, ID mapping will be activated, and the code expect file `users_id_mapping_configuration.yaml` to be present in the same folder.

This file must contain a list of users to map, between upstream Keycloack user, identified by an associated email, and the Slurm local user on the bare metal cluster.
An SSH private key must also be present to allow the downstream scheduler to ssh to the cluster on behalf of this user to submit jobs.

Example of file content:

```yaml
users_id_mapping:
  - user: Benoit Leveugle
    jarvice_user: bleveugleb
    mail: benoit.leveugle@eviden.net
    mapped_user: kirby
    ssh_private_key_b64: "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

Note: ssh_private_key_b64 is a base 64 encoded private key.

Ensure that for each user, the public key associated to the user private key is present in the `$HOME/.ssh/authorize_keys` of the user.

Note that the tool will only use the user account to call `sbatch` command. All other operations are done from the `jarvice` user account only.
