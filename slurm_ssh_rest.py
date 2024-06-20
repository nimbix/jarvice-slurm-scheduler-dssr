import os
import json
import io
import shlex
import urllib.parse
import paramiko
from base64 import b64encode, b64decode
import logging
import yaml

class baremetal_connector(object):

    def __init__(self):

        self.log = logging.getLogger(__name__)
        logging.basicConfig(encoding='utf-8', level=logging.DEBUG)

        self.baremetal_executor = os.getenv('JARVICE_BAREMETAL_EXECUTOR')

        # ############## Images handling ###############
        # Docker credentials to grab Jarvice images
        self.init_dockeruser = os.getenv('JARVICE_DOCKER_USERNAME', '')
        self.init_dockerpasswd = os.getenv('JARVICE_DOCKER_PASSWORD', '')
        # Http proxy for baremetal cluster to pull images
        self.baremetal_http_proxy = os.getenv(
            'JARVICE_BAREMETAL_HTTP_PROXY', "")
        self.baremetal_https_proxy = os.getenv(
            'JARVICE_BAREMETAL_HTTPS_PROXY', "")
        self.baremetal_no_proxy = os.getenv('JARVICE_BAREMETAL_NO_PROXY', "")
        self.sysregistry = os.environ['JARVICE_SYSTEM_REGISTRY']
        self.sysbase = os.environ['JARVICE_SYSTEM_REPO_BASE']
        self.appregistry = os.environ.get('JARVICE_LOCAL_REGISTRY', None)
        if self.appregistry:
            try:
                self.appbase = os.environ['JARVICE_LOCAL_REPO_BASE']
            except Exception:
                raise Exception('JARVICE_LOCAL_REGISTRY specified without ' +
                                'JARVICE_LOCAL_REPO_BASE')
        self.appproxyport = os.environ.get('JARVICE_REGISTRY_PROXY_PORT', None)
        if self.appproxyport:
            try:
                self.appproxybucket = os.environ['JARVICE_REGISTRY' +
                                                 '_PROXY_REPOS']
            except Exception:
                logging.info('JARVICE_REGISTRY_PROXY_PORT specified without ' +
                             'JARVICE_REGISTRY_PROXY_REPOS')

        # ############## Data handling ###############
        # We assume scratchdir to always end by an / in scripts later,
        # except if empty. path.join ensure path end with / if not empty
        self.scratchdir = os.path.join(os.getenv(
            'JARVICE_BAREMETAL_SCRATCH_DIR', ""), '')

        # ############## Singularity ###############
        # Enable/disable singularity and script verbosity
        self.singularity_verbose = os.getenv(
            'JARVICE_SINGULARITY_VERBOSE', 'false')
        # Singularity cache dir. Need a large one for huge apps.
        self.singularity_tmpdir = os.getenv(
            'JARVICE_SINGULARITY_TMPDIR', '/tmp')
        # Singularity overlay size
        self.overlay_size = os.getenv('JARVICE_SINGULARITY_OVERLAY_SIZE', 600)

        # ############## Slurm REST API ##############
        self.slurmrestd_host = os.environ['JARVICE_SLURMRESTD_ADDR']
        self.slurmrestd_port = os.environ['JARVICE_SLURMRESTD_PORT']
        self.slurmrestd_api_version = os.environ['JARVICE_SLURMRESTD_API_VERSION']

        # ############## SSH to slurm cluster ###############
        self.ssh_host = os.environ['JARVICE_SLURM_CLUSTER_ADDR']
        self.ssh_port = os.getenv('JARVICE_SLURM_CLUSTER_PORT', default=22)
        self.ssh_user = os.environ['JARVICE_SLURM_SSH_USER']
        self.ssh_pkey = os.environ['JARVICE_SLURM_SSH_PKEY']

        self.log.info('')
        self.log.info(self.init_dockeruser)
        self.log.info('+----- Slurm Scheduler init report -----+')
        self.log.info('|-- SSH connection to target cluster:')
        self.log.info(f'|     host: {self.ssh_host}')
        self.log.info(f'|     port: {self.ssh_port}')
        self.log.info(f'|     user: {self.ssh_user}')
        self.log.info('|-- HTTP API connection to target slurmrestd:')
        self.log.info(f'|     host: {self.slurmrestd_host}')
        self.log.info(f'|     port: {self.slurmrestd_port}')
        self.log.info(f'|     api_version: {self.slurmrestd_api_version}')
        self.log.info('|-- Script environment:')
        self.log.info(f'|     scratch dir: {self.scratchdir}')
        self.log.info(f'|     http_proxy: {self.baremetal_http_proxy}')
        self.log.info(f'|     https_proxy: {self.baremetal_https_proxy}')
        self.log.info(f'|     no_proxy: {self.baremetal_no_proxy}')
        self.log.info('|-- Singularity environment:')
        self.log.info(f'|     tmp work dir: {self.singularity_tmpdir}')
        self.log.info(f'|     verbose mode: {self.singularity_verbose}')
        self.log.info(f'|     overlay size: {self.overlay_size}')
        self.log.info('+---------------------------------------+')
        self.log.info('')
        self.log.info(' Now testing connectivity to target cluster...')
        try:
            self.ssh('/bin/true')
            self.log.info(' Success! :)')
        except Exception as e:
            self.log.warning(' SSH failed: %s' % str(e))
            self.log.warning(' Could not connect to remote cluster! :(')
            self.log.warning(' Please check ssh parameters.')
        self.log.info(' Now testing connectivity to target cluster slurmrestd...')
        try:
            stdout, stderr = self.ssh("curl " + self.slurmrestd_host + ":" + self.slurmrestd_port + "/")
            if "Authentication failure" in stderr or "Authentication failure" in stdout:
                self.log.info(' Success! :)')
            else:
                self.log.info(' Could ssh to cluster but could not reach slurmrestd :(')
        except Exception as e:
            self.log.warning(' SSH failed: %s' % str(e))
            self.log.warning(' Could not connect to remote cluster! :(')
            self.log.warning(' Please check ssh parameters.')
        self.log.info('\n Init done. Entering main loop.')

    def users_mapping(self, username):
        
        umapping = yaml.safe_load("users_mapping.yaml")['users_mapping']
        mapped_username = None
        for user in umapping:
            if user["mail"] == username: # TO BE UPDATED ONCE TOKEN HERE
                mapped_username = user["local_user"]

        return mapped_username

    def gc(self):
        """ garbage collection endpoint; fail if cluster not reachable """
        try:
            self.ssh('/bin/true')
            return 200
        except Exception:
            return 500

    def running(self):
        """ returns list of running jobs as [(name, jobid), ...]"""
        return self.squeue(user=self.ssh_user, states='R,RH,RS,SI,ST,S,CG,SO')

    def queued(self):
        """ returns list of queued jobs as [(name, jobid), ...]"""
        return self.squeue(user=self.ssh_user, states='PD,RD,RF')

    def exitstatus(self, name, number, jobid):
        """ returns exit status of a completed job """

        # 2 ways to gather job status:
        # - squeue: fast, but prone to lose job data once job ended,
        # as jobs don't live in squeue for very long
        # - sacct: slower, but always keep job data
        # Try squeue and fallback to sacct if failed.
        # If both failed, consider job canceled.

        # Try squeue
        self.log.debug(f'Getting exit status via squeue for {jobid}',
                       exc_info=True)
        state, elapsed, nodes = self.squeue1(jobid, self.ssh_user)
        if state is not None:
            if state in ['F', 'NF', 'OOM']:
                # completed with error
                rc = 1
            elif state in ['DL', 'PR', 'CA']:
                # explicitly canceled (TERMINATED in JARVICE terms)
                rc = -15
            elif state == 'CD':
                # successful completion
                rc = 0
            else:
                # some other termination - consider it canceled
                # in JARVICE terms
                rc = -9
        # Try sacct
        else:
            self.log.debug(f'Getting exit status via sacct for {jobid}',
                           exc_info=True)
            stdout, stderr = self.ssh(
                'sacct --jobs=%s --format=state,elapsed | sed -n 3p | xargs'
                % jobid)
            if 'disabled' not in stderr and len(stderr) == 0:
                state, elapsed = stdout.split(' ')
                if state in ['FAILED', 'NODE_FAIL', 'OUT_OF_MEMORY']:
                    # completed with error
                    rc = 1
                elif state in ['DEADLINE', 'PREEMPTED', 'CANCELLED']:
                    # explicitly canceled (TERMINATED in JARVICE terms)
                    rc = -15
                elif state == 'COMPLETED':
                    # successful completion
                    rc = 0
                else:
                    # other termination - consider canceled in JARVICE terms
                    rc = -9
            else:
                # Cannot grab data - job probably never ran
                # or sacct not available and squeue lost it
                return -9, '00:00:00', []

        # If we reach that point, we got a state
        # fetch and clean output - last 10k lines only
        stdout, stderr = self.ssh(
            'tail -10000 %s.out' % (self.scratchdir + '.jarvice/' + name))
        outs = [stdout,
                '<< termination state: %s -- see STDOUT for job errors >>' %
                state]

        # Kubernetes object cleanup (if applicable)
        self.gc_job(name, number, jobid)

        return rc, elapsed, outs

    def runstatus(self, name=None, number=None, jobid=None, nc={}):
        """ returns running status of a single job """
        state, elapsed, nodes = self.squeue1(jobid, self.ssh_user)
        if state is None:
            return None, None, None, None

        return (nodes, elapsed, name + '/' + str(number) + '/' + jobid, None
                ) if state else (None, None, None, None)

    def terminate(self, name, number, jobid, force=False, nodes=[]):
        """ terminates a job """
        # XXX: SIGTERM doesn't seem to work at all, so default to SIGKILL
        # regardless of force - was:
        #    self.ssh('scancel -s %d %s' % (9 if force else 15, jobid))
        self.log.info(f'Terminating job: {jobid}')
        self.ssh('scancel -f ' + jobid)

#         terminate_cmd = """
# curl -X DEL {slurmrestd_host}:{slurmrestd_port}/slurm/{slurmrestd_api_version}/job/{jobid} \
# -H "X-SLURM-USER-NAME:{username}" \
# -H "X-SLURM-USER-TOKEN:{jwt_token}"
# """.format(
#         slurmrestd_host=self.slurmrestd_host,
#         slurmrestd_port=self.slurmrestd_port,
#         slurmrestd_api_version=self.slurmrestd_api_version,
#         jobid=jobid,
#         username=self.job_mapped_user,
#         jwt_token=os.getenv('SLURM_JWT')
#     )
#         stdout, stderr = self.ssh(terminate_cmd)

        return True  # best effort

    def online(self, host, status=True, comment=''):
        """ sets a node online or offline - legacy """
        return status

    def release(self, name, number, jobid):
        """ releases a held job """
        stdout, stderr = self.ssh(f'scontrol release {jobid}')
        if stderr:
            raise Exception(f'Releasing job failed: {stderr}')
        return True  # Best effort

    def events(self, name, number, jobid):
        """ returns list of events associated with job """
        # what's most useful to the admin here is the scontrol job output;
        # while not exactly events, it can show what's happening with a job
        stdout, stderr = self.ssh(f'scontrol show job {jobid}')
        if not stdout:
            raise Exception(f'squeue failed: {stderr}')
        return stdout

    def request(self, path, qs):
        """ handle arbitrary request to the scheduler """

        # response helpers
        def rsp(code, content_type=None, content=None):
            return code, content_type, content

        def rsp_json(code, dct):
            self.log.info("rsp_json")
            return rsp(code, 'application/json', json.dumps(dct))

        # check non-job related paths
        method = path.lstrip('/').rstrip('/')
        if method == 'pvcls':

            # "PVC" here just means a locally mounted path; subpath is treated
            # as absolute path instead; also note that we add a fake /data
            # in front since this is what upstream is expecting and strips
            path = shlex.quote(qs['path'][0]) if 'path' in qs else ''
            details = 'details' in qs and qs['details'][0].lower() == 'true'
            if details:
                findstr = ('cd / && /usr/bin/find ' + path + ' -type d ' +
                           '-maxdepth 1 ' +
                           '-exec /bin/stat -c "%Y %s /data%n/" {} \\; && ' +
                           '/usr/bin/find ' + path + ' -type f ' +
                           '-maxdepth 1 ' +
                           '-exec /bin/stat -c "%Y %s /data%n" {} \\;')
            else:
                findstr = ('cd / && /usr/bin/find ' + path + ' -type d ' +
                           '-maxdepth 1 -exec /bin/echo /data{}/ \\; && ' +
                           '/usr/bin/find ' + path + ' -type f ' +
                           '-maxdepth 1 -exec /bin/echo /data{} \\;')
            stdout, stderr = self.ssh(findstr)
            return rsp(200 if stdout else 401,
                       content_type='text/plain',
                       content=str(stdout if stdout else stderr))

        # kind of REST-y: jobname and job ID are encoded in path
        try:
            jobname, jobnum, jobid, method = path.lstrip('/').split('/')
        except Exception:
            self.log.info('path decode failed')
            return rsp(400)
        self.log.debug("jobname " + jobname)
        self.log.debug("jobnum " + jobnum)
        self.log.debug("jobid " + jobid)
        self.log.debug("method " + method)

        # methods
        if method == 'ping':
            pass
        elif method == 'shutdown' or method == 'abort':
            self.terminate(jobname, None, jobid, force=(method == 'abort'))
        elif method == 'connect':
            pass
        elif method == 'info':
            # Batch only
            readyjson = {'about': '', 'help': '', 'url': '', 'actions': {}}
            return rsp_json(200, readyjson)
        elif method == 'tail':
            try:
                lines = int(qs['lines'][0])
                assert (lines > 1)
            except Exception:
                lines = 100
            stdout, stderr = self.ssh(
                'tail -%d %s.jarvice/%s.out' % (lines,
                                                self.scratchdir, jobname))
            return rsp(200, content_type='text/plain',
                       content=stdout) if stdout else rsp(404)

        # catch-all
        return rsp(200)

    # Submit a job
    def submit(self, name, number, nodes, hpc_script, bearer, held=False):
        """ submits a job for scheduling

        Input:
        - name (str): name of the job
        - number (int): number associated to the job
        - hpc_script (str): script to be passed to job scheduler

        Ouput:
        - job name (str): job name provided by bare metal scheduler

        """
        try:
            self.log.info(f'Job submittion request for {name}:{number}')

            # Grab executor script only, and decode it
            hpc_script = b64decode(
                hpc_script[self.baremetal_executor]).decode('utf-8')
            connection_string = """
    # --------------------------------------------------------------------------
    # Main parameters from baremetal Dowstream
    # This part is dynamic
    # and can be adapted to any kind of bare metal job scheduler
    # See this section as a "connector"

    # Global parameters
    export JARVICE_JOB_SCRATCH_DIR={JARVICE_BAREMETAL_SCRATCH_DIR}
    export SINGULARITYENV_JARVICE_SERVICE_PORT={JARVICE_SERVICE_PORT}
    export SINGULARITYENV_JARVICE_SSH_PORT={JARVICE_SSH_PORT}
    export JARVICE_SINGULARITY_TMPDIR={JARVICE_SINGULARITY_TMPDIR}

    # User
    export JOB_LOCAL_USER={JOB_LOCAL_USER}

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
    """

            def find_key(script2search, key2find):
                """
                Basic function to search in hpc_script a specific key
                and extract its value
                """
                for line2search in script2search.splitlines():
                    if len(line2search.split("=")) >= 2 and \
                    line2search.split("=")[0] == key2find:
                        if str(line2search.split("=")[1]) == "":
                            return None
                        return str(line2search.split("=", 1)[1])
                return None

            self.jobobj_interactive = find_key(hpc_script, "JOBOBJ_INTERACTIVE")
            if self.jobobj_interactive == "False":
                self.jobobj_interactive = bool(False)
            else:
                self.jobobj_interactive = bool(True)
            self.jobobj_appdefversion = int(
                find_key(hpc_script, "JOBOBJ_APPDEFVERSION"))
            self.jobobj_arch = find_key(hpc_script, "JOBOBJ_ARCH")
            self.jobobj_nae = find_key(hpc_script, "JOBOBJ_NAE")
            self.jobobj_repo = find_key(hpc_script, "JOBOBJ_REPO")
            self.jobobj_ctrsecret = find_key(hpc_script, "JOBOBJ_CTRSECRET")
            self.jobobj_user = find_key(hpc_script, "JOBOBJ_USER")
            self.jobobj_docker_secret = find_key(
                hpc_script, "JOBOBJ_DOCKER_SECRET")
            if self.jobobj_docker_secret is not None:
                try:
                    self.jobobj_docker_secret = json.loads(
                        self.jobobj_docker_secret)
                except json.decoder.JSONDecodeError:
                    self.jobobj_docker_secret = {}
            else:
                self.jobobj_docker_secret = {}
            self.jobobj_devices = find_key(hpc_script, "JOBOBJ_DEVICES")
            if self.jobobj_devices is not None:
                try:
                    self.jobobj_devices = json.loads(self.jobobj_devices)
                except json.decoder.JSONDecodeError:
                    self.jobobj_devices = {}
            else:
                self.jobobj_devices = {}
            self.jobobj_gpus = find_key(hpc_script, "JOBOBJ_GPUS")
            if self.jobobj_gpus is not None:
                self.jobobj_gpus = int(self.jobobj_gpus)
            else:
                self.jobobj_gpus = 0
            self.jobobj_ram = find_key(hpc_script, "JOBOBJ_RAM")
            if self.jobobj_ram is not None:
                self.jobobj_ram = int(self.jobobj_ram)
            else:
                self.jobobj_ram = 0
            self.jobobj_licenses = find_key(hpc_script, "JOBOBJ_LICENSES")
            self.jobobj_walltime = find_key(hpc_script, "JOBOBJ_WALLTIME")
            self.jobobj_cores = int(find_key(hpc_script, "JARVICE_CPU_CORES"))
            jarvice_cmd = find_key(hpc_script, "JARVICE_CMD")

            if self.jobobj_appdefversion < 2:
                return 'Appdef V2+ is required for this downstream', 400

            if self.jobobj_interactive and not self.jobsdomain:
                return 'interactive jobs are not supported on this cluster', 400
            print('2')

            # USER ID MAPPING
            self.job_mapped_user = self.users_mapping(self.jobobj_user)

            # determine appropriate Docker secret
            def get_reg(url):
                scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)
                return netloc if netloc else url

            # Find registry credentials in whole auths map
            def get_reg_auth(auths, reg):
                user = ""
                passwd = ""
                for i in auths.keys():
                    if reg == get_reg(i):
                        try:
                            parts = b64decode(
                                auths[i]['auth']).decode('utf-8').split(
                                    ':', maxsplit=1)
                            user = parts[0]
                            passwd = parts[1]
                            self.log.info(
                                f'Using system/user Docker secret for {reg}')
                        except Exception as e:
                            self.log.info(
                                f'Failed to parse docker secret for {i}: {e}')
                            pass
                return user, passwd

            # ####### INIT IMAGE

            def goarch(arch=None):
                '''
                Returns the Go architecture for a given system architecture

                Args:
                    arch - architecture to get, or None to get the current node's

                Returns:
                    Go architecture for arch
                '''
                if arch is None:
                    arch = os.uname()[4]

                # convert what we need to
                if arch == 'x86_64':
                    return 'amd64'
                else:
                    return arch

            def imgtag(arch, default_tag='latest'):
                '''
                Returns a different container image tag if using explicit
                architectures in container image tags, to reflect a desired
                architecture; computes from ${JARVICE_IMAGES_TAG} if set

                Args:
                    arch    - desired architecture

                Returns:
                    New container image tag, if original tag is single arch;
                    original tag if not;
                    if there is no original tag, returns <default_tag>-<arch>
                '''
                tag = os.environ.get('JARVICE_IMAGES_TAG', default_tag)
                thisarch = goarch()
                alen = len(thisarch)
                return (
                    tag[:-alen] + arch if len(tag) > (alen + 1)
                    and tag[-alen:] == thisarch
                    else tag)

            # Grab init image, and related credentials (if any)
            init_image = (self.sysregistry + "/" + self.sysbase + "/initv" +
                        str(self.jobobj_appdefversion) + ":" +
                        imgtag(goarch(self.jobobj_arch)))
            jarvice_init_image = 'docker://' + init_image
            init_dockeruser = b64decode(self.init_dockeruser).decode('utf-8')
            init_dockerpasswd = b64decode(self.init_dockerpasswd).decode('utf-8')

            # ####### APP IMAGE

            # Grab app image
            if self.appregistry:
                # Caching mode deployment - image in local registry
                app_image = (self.appregistry + '/' + self.appbase + '/' +
                            self.jobobj_nae + ':latest')
            elif self.appproxyport:
                app_image = self.jobobj_repo
                # override app repo with proxy if found
                for proxy in self.appproxybucket.split(','):
                    if self.jobobj_repo.startswith(proxy):
                        app_proxy = 'localhost:' + self.appproxyport
                        app_image = self.jobobj_repo.replace(proxy.split('/')[0],
                                                            app_proxy, 1)
                        break
            else:
                # Remote mode deployment - image is in its original registry
                app_image = self.jobobj_repo

            jarvice_app_image = 'docker://' + app_image

            # Grab app image credentials (if any)
            if self.jobobj_ctrsecret is not None:
                auths = json.loads(b64decode(
                    self.jobobj_ctrsecret).decode('utf-8')).get('auths', {})
            else:
                auths = {}
            self.log.debug(
                f'Docker registry secrets available for: {list(auths.keys())}')
            ds = self.jobobj_docker_secret
            if ds:
                self.log.debug(
                    f'Docker registry secret for job container for {ds["server"]}')
            parts = self.jobobj_repo.split('/')
            reg = get_reg(parts[0]) if len(parts) > 2 else 'index.docker.io'
            dockeruser = ''
            dockerpasswd = ''
            if ds and reg == get_reg(ds['server']):

                # matches the job-specific secret for the app owner
                dockeruser = ds['username']
                dockerpasswd = ds['password']
                self.log.debug(f'Using job/app-specific Docker secret for {reg}')
            else:
                dockeruser, dockerpasswd = get_reg_auth(auths, reg)

            self.log.info("JARVICE_CMD")
            self.log.info(jarvice_cmd)

            # Port is hard-coded for this simple version
            ssh_port = 2222
            svc_port = 7778

            script = hpc_script.format(
                DOWNSTREAM_PARAMETERS=connection_string.format(
                    JARVICE_BAREMETAL_SCRATCH_DIR=self.scratchdir,
                    JARVICE_SERVICE_PORT=svc_port,
                    JARVICE_SSH_PORT=ssh_port,
                    JARVICE_SINGULARITY_TMPDIR=self.singularity_tmpdir,
                    JARVICE_SINGULARITY_OVERLAY_SIZE=self.overlay_size,
                    JARVICE_APP_IMAGE=jarvice_app_image,
                    JARVICE_INIT_IMAGE=jarvice_init_image,
                    JARVICE_DOCKER_USERNAME=b64encode(
                        bytes(dockeruser, 'utf-8')).decode('utf-8'),
                    JARVICE_DOCKER_PASSWORD=b64encode(
                        bytes(dockerpasswd, 'utf-8')).decode('utf-8'),
                    JARVICE_INIT_DOCKER_USERNAME=b64encode(
                        bytes(init_dockeruser, 'utf-8')).decode('utf-8'),
                    JARVICE_INIT_DOCKER_PASSWORD=b64encode(
                        bytes(init_dockerpasswd, 'utf-8')).decode('utf-8'),
                    JARVICE_BAREMETAL_HTTP_PROXY=self.baremetal_http_proxy,
                    JARVICE_BAREMETAL_HTTPS_PROXY=self.baremetal_https_proxy,
                    JARVICE_BAREMETAL_NO_PROXY=self.baremetal_no_proxy,
                    JARVICE_CMD=jarvice_cmd,
                    SINGULARITY_VERBOSE=self.singularity_verbose,
                    JOB_LOCAL_USER=self.job_mapped_user
                )
            )

            # Now enter slurm special part

            # First encapsulate the script:

            dynamic_scheduler_mapping = """
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
        """

            srun_start = r"""#!/bin/bash
    echo "Hello from $(hostname)"
    echo "Entering parallel region"

    exec 5>&1
    FF=$(srun -K1 --export=ALL -N $SLURM_NNODES \
    -n $SLURM_NNODES --ntasks-per-node=1 /bin/bash -c '
    set -x

        """

            srun_end = r"""

    ' 2>&1 | tee >(cat - >&5) )

    ############################################################################
    #############  EXIT CODE CHECKING
    ####
    # srun commands return exit code of last instance exited,
    # which is not what we need.
    # We need to grab instance 0 exit code. To do so, we need to analyse output.
    # WARNING: any changes to verbosity level will break this mechanism.

    [ "$SV" = "true" ] && echo "[$SLURM_PROCID] Post scripts - exit code analysis"
    echo $FF\
    | grep -v 'GoTTY is starting with command'\
    | sed 's/\/bin\/echo\ JARVICE_CMD_SUCCESS//'\
    | sed 's/\/bin\/echo\ JARVICE_CMD_FAILURE//'\
    | grep --quiet 'JARVICE_CMD_SUCCESS'
    if [ $? -eq 0 ]; then
        echo JARVICE Job completed OK
        exit 0
    else
        echo JARVICE Job failed, investigate logs
        exit 1
    fi
        """

            script = srun_start + dynamic_scheduler_mapping + script + srun_end

            # Now build sbatch parameters

            # devices/pseudo-devices...
            # note that since most of this is not relevant in Slurm clusters,
            # we'll use it for special functionality like container configuration
            # and scheduler parameters
            # also note that we want to fail job submission if there are parameter
            # errors so that erroneous jobs don't run unintentionally
            sbatch_add_params = ''
            slurm_part = ''
            slurm_exclusive = True
            for i in self.jobobj_devices:
                try:
                    k, v = i.split('=')
                    k = k.strip()
                    v = v.strip()
                except Exception:
                    raise Exception(f'Malformed (pseudo)device: {i}')

                if k == 'overlay':
                    try:
                        self.overlay_size = int(v)
                        assert self.overlay_size >= 0
                    except Exception:
                        raise Exception(
                            f'Invalid overlay setting {v}: must be integer >=0')
                elif k == 'partition':
                    slurm_part = v
                elif k == 'exclusive':
                    if v == 'False':
                        slurm_exclusive = False
                elif k.startswith('sbatch_'):
                    sbatch_add_params = (
                        sbatch_add_params +
                        ' --' + k.replace('sbatch_', '') +
                        '=' + str(v)
                        )
                else:
                    raise Exception(
                        f'Unknown (pseudo)device specified: {k}')

            # job other limits: mem and gpus
            slurm_gpus = ''
            slurm_mem = ''
            if self.jobobj_gpus > 0:
                slurm_gpus = str(self.jobobj_gpus)
            if self.jobobj_ram > 0:
                slurm_mem = str(self.jobobj_ram)

            if (self.jobobj_interactive or slurm_gpus) and not slurm_exclusive:
                self.log.info(
                    'interactive or GPU job forcing the use of node exclusivity!')
                slurm_exclusive = True

            # optional licenses
            licenses = self.jobobj_licenses  # jobself.get('licenses', None)

            # optional walltime
            slurm_time = self.jobobj_walltime  # str(jobself.get('walltime', ''))
            if str(slurm_time) == 'None':
                slurm_time = ''

            # Submit job
            # Note to developers:
            # Current mechanism starts 1 singularity container per node.
            # To allocate job CPU Cores resources, considering that mechanism,
            # -n {jobobj['cores'] * nodes} -N {nodes} are passed to sbatch (so
            # Slurm will allocate these cores to the job), but srun command will
            # run with -n {nodes} -N {nodes} --task-per-node=1, to ensure a unique
            # singularity start per node.
            # self.log.info(f'Submitting job {name}:{number} via sbatch')
            # self.log.info('Submitted script:\n' + script)

            self.log.info(f'Submitting job {name}:{number} via sbatch')
            self.log.debug('Submitted script:')
            self.log.debug('--------------------------------------------------')
            self.log.debug(script)
            self.log.debug('--------------------------------------------------')

            # Building HTTP request
            try:
            # "script": "#!/bin/bash\\necho 'ZWNobyBoZWxsbyAmJiBob3N0bmFtZSAmJiBlY2hvICRDT0xPUgo=' | base64 -d | srun -K1 --export=ALL -N 1 -n 1 --ntasks-per-node=1 /bin/bash && srun /bin/bash -c 'hostname && sleep 360'",

                # Encoding script
                encoded_script = b64encode(script.encode("utf8")).decode("utf8")

                job_json = """
    {{
        "script": "#!/bin/bash\\necho '{encoded_script}' | base64 -d | /bin/bash",
        "job": {{
            "time_limit": {{
                "number": 5,
                "set": True,
                "infinite": False
            }},
            "exclusive": ["true","true"],
            "nodes": "1",
            "memory_per_node" : {{
                "number" : 1,
                "set" : True,
                "infinite" : False
            }},
            "partition": "all",
            "tasks": 2,
            "current_working_directory": "{scratchdir}/{username}/",
            "standard_output": "{scratchdir}/{username}/{job_name}.out",
            "standard_error": "{scratchdir}/{username}/{job_name}.out",
            "name": "jarvice_{job_name}",
            "environment": [
                "JARVICE=true"
            ],
            "hold": False
        }}
    }}
    """.format(
            job_name=name,
            encoded_script=encoded_script,
            scratchdir=self.scratchdir,
            username=self.job_mapped_user
        )

    #         "tres_per_node":"gres/gpu=1",

                submit_cmd = """
    mkdir -p $HOME/.jarvice &&\
    curl -X POST {slurmrestd_host}:{slurmrestd_port}/slurm/{slurmrestd_api_version}/job/submit \
    -H "X-SLURM-USER-NAME:{username}" \
    -H "X-SLURM-USER-TOKEN:{jwt_token}" \
    -H "Content-Type: application/json" \
    -d @- <<- EOF
    {job_json}
    EOF
    """.format(
            slurmrestd_host=self.slurmrestd_host,
            slurmrestd_port=self.slurmrestd_port,
            slurmrestd_api_version=self.slurmrestd_api_version,
            job_json=job_json,
            username=self.job_mapped_user,
            jwt_token=bearer # os.getenv('SLURM_JWT')
        )
                print(submit_cmd)
            except Exception as e:
                print('Could not generate job json or cmd: ' + str(e))
            stdout, stderr = self.ssh(submit_cmd)

            if not stdout:
                # self.pmgr.unreserve(number)  --> BEN
                raise Exception(
                    'submit(): sbatch: ' + stderr.replace('\n', ' -- '))

            job_id = json.loads(stdout)['job_id']

            # remove sensitive lines from script before storing
            slines = [
                'export SINGULARITY_DOCKER_USERNAME=',
                'export SINGULARITY_DOCKER_PASSWORD=']
            fscript = ''
            for i in script.splitlines():
                if not [x for x in slines if x == i[:len(x)]]:
                    fscript += (i + '\n')

            return job_id, fscript
        except Exception as e:
            # In case of errors, these are often cryptique in this section
            # We want to pass a max of infos to ease debug.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print('ERROR!!!')
            print(exc_type, fname, exc_tb.tb_lineno)
            return jsonify(
                (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
                '\n' + str(exc_tb.tb_lineno))), 400

    def gc_job(self, name, number, jobid, cancel=False):
        """ garbage collects slurm and k8s objects for a single job """
        # cancel Slurm job if asked
        if cancel:
            self.log.info(f'Cancelling job: {jobid}')
            self.ssh('scancel -f ' + jobid)

        # Slurm objects (best effort)
        self.log.info(f'Garbage collecting job: {jobid}')
        self.ssh('/bin/sh -c "nohup rm -Rf %s.out %s >/dev/null 2>&1 &"' % (
            self.scratchdir + '.jarvice/' + name,
            self.scratchdir + '.jarvice/jobs/' + jobid))

    def squeue(self, user=None, states=None):
        """ runs squeue (with optional filters) and returns parsed list """

        # TODO: filter only jobs that we have started

        queue = []
        fmt = '%j|%A'
        cmd = 'squeue --noheader'
        if user:
            cmd += (' -u "%s"' % user)
        else:
            fmt += '|%u'
        if states:
            cmd += (' -t "%s"' % states)
        else:
            fmt += '|%t'
        cmd += (' -o "%s"' % fmt)
        stdout, stderr = self.ssh(cmd)
        for line in stdout.splitlines():
            if line.startswith('jarvice_'):
                queue.append(line[8:].split('|'))
        return queue

    def squeue1(self, jobid, user=None):
        """ returns job info on a single job """
        cmd = 'squeue --noheader -o "%%t|%%M|%%N" -j %s -t all' % jobid
        if user:
            cmd += ' -u "%s"' % user
        stdout, stderr = self.ssh(cmd)
        try:
            state, elapsed, nodes = stdout.split('|')
            nodes = nodes.split(',')

            # Time can be in multiple format:
            # mm:ss
            # hh:mm:ss
            # dd-hh:mm:ss
            # normalize elapsed time into HH:MM:SS regardless of what we get

            if '-' in elapsed:  # Days are provided
                days = int(elapsed.split('-')[0])
                elapsed = elapsed.split('-')[1]
            else:
                days = 0

            if len(elapsed.split(':')) == 3:
                hours = int(elapsed.split(':')[0]) + days * 24
                mins = int(elapsed.split(':')[1])
                secs = int(elapsed.split(':')[2])
            else:
                hours = 0
                mins = int(elapsed.split(':')[0])
                secs = int(elapsed.split(':')[1])

            elapsed = '%02d:%02d:%02d' % (hours, mins, secs)

            return state, elapsed, nodes

        except Exception:
            logging.warning('failed to fetch job info for %s' % jobid)
            return None, None, None

    def ssh_key_load(self, ssh_pkey):
        """ returns private key, either RSA or ED25519 """
        try:
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_pkey))
            return pkey
        except paramiko.SSHException:
            pass
        try:
            pkey = paramiko.Ed25519Key.from_private_key(io.StringIO(ssh_pkey))
            return pkey
        except paramiko.SSHException:
            pass
        raise ValueError("Unsupported key type")

    def ssh(self, cmd, instr=None):
        """ SSH's to slurm cluster and returns stdout/stderr """

        with paramiko.client.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self.ssh_host, username=self.ssh_user,
                port=self.ssh_port,
                pkey=self.ssh_key_load(self.ssh_pkey))

            self.log.info(
                'ssh -p %s %s@%s %s' % (str(self.ssh_port),
                                        self.ssh_user, self.ssh_host, cmd))
            stdin, stdout, stderr = client.exec_command(cmd)
            if instr:
                stdin.write(instr.encode())
            stdin.close()
            stdout = stdout.read().decode().rstrip()
            stderr = stderr.read().decode().rstrip()
            if len(stdout) > 1:
                self.log.info('stdout: %s' % stdout)
            if len(stderr) > 1:
                self.log.info('stderr: %s' % stderr)
            return stdout, stderr
