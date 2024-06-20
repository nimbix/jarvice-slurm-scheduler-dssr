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

Kubernetes pods management natively used in Jarvice is replaced here by usage of Singularity or any other similar baremetal tool.

## Requirements

This service can run on any kind of system, even Microsoft Windows.

Needed pip3 dependencies:

```
pip3 install json waitress flask paramiko yaml
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
          │   Baremetal      │
          │    connector     │
          │                  │
          └────────┬─────────┘
                   │
                   │
               ssh │
                   │
                   ▼
        ┌─────────────────────┐
        │ Bare metal          │
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

## Connectors

### Slurm connector

The Slurm connector is for now the default one. It is able to submit jobs to a bare metal slurm cluster, using both CLI and REST HTTP interfaces of slurm.

#### Slurm cluster setup

##### The Jarvice user

A specific user must be created on the target cluster. Default name is `jarvice`. This user acts as the ssh entry point to the cluster, and will be used to manage jobs (submitting, releasing, terminating, grabbing logs, etc.).

The user MUST have the same uid on the whole cluster, and so should be configured like any other traditional unpriviledged users (LDAP, etc).

##### SSH keys to connect to the cluster

Once user has been created, an ssh key couple is needed. Generate a new key pair, without passphrase:

```
ssh-keygen -t ed25519 -f ./jarvice_id_ed25519 -q -N ""
```

Grab `jarvice_id_ed25519` content, this will be needed as `JARVICE_SLURM_SSH_PKEY` later.

Then grab `jarvice_id_ed25519.pub` content, and add it to authorized_keys of the Jarvice user on the slurm cluster.

##### Accounts coordinator

The Jarvice user `jarvice` must be set **coordinator** of every accounts that contains users using Jarvice portal. This allows the Jarvice user to see associated accounts jobs (even if `PrivateData` key is set in slurm.conf), and release or terminate them.

Assuming the slurmdbd daemon is running and properly configured, and that a cluster has been created on the target cluster, here is the procedure to create accounts, add users to accounts, and set Jarvice user as coordinator of these accounts. Please adapt to your needs:

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

##### Scratch structure

A scratch must be setup for:

1. Images cache (shareds and privates)
2. Images pull locks (shareds and privates)
3. Jobs temporary files (private)
4. Jobs logs storage (private)

While each user must be contained in its own directory in the Jarvice dedicated scratch, the `jarvice` user must be able to read/write in all users' jarvice scratch.
This mechanism requires usage of file system ACLs.

We will assume here that jarvice dedicated scratch path is `/jxe_scratch`, and that this directory is mounted on all `slurmd` workers, and on the node where `jarvice` user is operating (where downstream ssh into to operate). We also assume the file system is compatible with Linux ACL.

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

Last step is to make `jarvice` user able to read and write also in to this user dedicated jarvice scratch. It is important to note that we configure it as default ACL, so that this ACL is propagated to any newly created subfolder and files later.

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

Repeat this for each users so that each Jarvice user posses her/his own Jarvice scratch folder, also read/writable by `jarvice` user.
The `/jxe_scratch` directory will have to be set later as `JARVICE_BAREMETAL_SCRATCH_DIR` environment variable of the downstream scheduler.

#### Downstream environment variables

Now that everything is configured on the slurm bare metal cluster, and that the `jarvice` user is created along with all the requirements, it is time to setup the downstream scheduler and launch it.

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
