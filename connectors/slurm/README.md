
## 5. Connectors

### 5.1. Slurm connector

The Slurm connector is able to submit jobs to a bare metal slurm cluster, using both CLI and REST HTTP interfaces of Slurm.

Note however that REST HTTP way is experimental and not considered stable for now.

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

#### Downstream configuration

Now that everything is configured on the slurm bare metal cluster, and that the `jarvice` user is created along with all the requirements, some settings are required for the slurm connector.

The Slurm connector encapsulate the script provided by upstream by adding `srun` command, and also adding dynamic Slurm's environment mapping the the script.

It uses ssh to connect to target cluster, and submit jobs via 2 methods:

1. Using CLI sbatch. If using this method, the slurm connector will rely on users id mapping (see bellow) to directly ssh to users accounts and submit jobs from there.
2. Using slurmrestd HTTP POST request. If using this method, the slurm connector will not use id mapping, but use the jarvice user to submit jobs using the bearer token received from upstream.

User can define method to be used by setting `JARVICE_SLURM_INTERFACE` environment variable to either `cli` either `http`. (Default is cli, and http is experimental)

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
