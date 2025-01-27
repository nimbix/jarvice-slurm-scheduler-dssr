import sqlite3
import os
import time
import random
import datetime
import json
from contextlib import closing

class baremetal_connector(object):



    def __init__(self):
        # Max job time in second
        self.job_running_time = int(os.getenv('JARVICE_DUMMY_JOB_RUNNING_TIME', '10'))
        # Queued job time in second
        self.job_queued_time = int(os.getenv('JARVICE_DUMMY_JOB_QUEUED_TIME', '5'))
        # Percent of failing jobs (random with probability based on this ratio)
        self.job_failing_percent = int(os.getenv('JARVICE_DUMMY_JOB_FAILING_PERCENT', '50'))
        # Make jobs interactive and return a fake url
        self.jobs_are_interactive = os.getenv('JARVICE_JOBS_ARE_INTERACTIVE', 'False')

        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute("CREATE TABLE IF NOT EXISTS jobs (name TEXT, number INTEGER, jobid TEXT, starttime INTEGER)")

        print('Dummy init done, db created or exists')

    def gc(self):
        """ garbage collection endpoint; fail if cluster not reachable """
        # Check we can dialogate with DB, since its our fake cluster
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    cursor.execute("PRAGMA integrity_check")
                except sqlite3.DatabaseError:
                    return 500
                return 200

    def submit(self, name, number, nodes, hpc_script, bearer, held=False):
        """ submits a job for scheduling """
        # For this dummy code, submitting a job is just adding it in the DB, with start time from epoch (time.time())
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    entry = "INSERT INTO jobs VALUES " + str((name, str(number), "dummy_" + str(number), str(int(time.time()))))
                    cursor.execute(entry)
                    connection.commit()
                except sqlite3.Error as e:
                    raise Exception(e) 
                return "dummy_" + str(number), entry

    def queued(self):
        """ returns list of queued jobs as [(name, jobid), ...]"""
        queueds = []
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    jobs = cursor.execute("SELECT name, number, jobid, starttime FROM jobs").fetchall()
                    current_time = int(time.time())
                    for job in jobs:
                        job_starttime = int(job[3])
                        if current_time - job_starttime < self.job_queued_time :
                            queueds.append([job[0], job[2]])
                except sqlite3.Error as e:
                    raise Exception(e) 
                return queueds

    def running(self):
        """ returns list of running jobs as [(name, jobid), ...]"""
        queueds = []
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    jobs = cursor.execute("SELECT name, number, jobid, starttime FROM jobs").fetchall()
                    current_time = int(time.time())
                    for job in jobs:
                        job_starttime = int(job[3])
                        if (current_time - job_starttime > self.job_queued_time ) and (current_time - job_starttime < self.job_queued_time + self.job_running_time) :
                            queueds.append([job[0], job[2]])
                except sqlite3.Error as e:
                    raise Exception(e) 
                return queueds

    def exitstatus(self, name, number, jobid):
        """ returns exit status of a completed job """
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    # Grab job from database by name
                    job = cursor.execute("SELECT name, number, jobid, starttime FROM jobs WHERE name = ?", (name,),).fetchall()
                    # Now delete job from database, this is garbage collect step
                    cursor.execute("DELETE FROM jobs WHERE name = ?", (name,))
                    connection.commit()
                except sqlite3.Error as e:
                    raise Exception(e) 
        # Ok, should the job be considered COMPLETED or FAILED ?
        if random.randint(0, 100) < self.job_failing_percent :
            rc = 1
            state = "ERROR"
        else:
            rc = 0
            state = "COMPLETED"
        totaltime = str(datetime.timedelta(seconds=(self.job_queued_time + self.job_running_time)))
        stdout = "This is job " + str(name) + "\nAnd I runned for " + totaltime
        state = '<< termination state: %s -- see STDOUT for job errors if any >>' % state
        return rc, totaltime, [stdout, state]

    def runstatus(self, name=None, number=None, jobid=None, nc={}):
        """ returns running status of a single job """
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    # Grab job from database by name
                    job = cursor.execute("SELECT name, number, jobid, starttime FROM jobs WHERE name = ?", (name,),).fetchall()
                except sqlite3.Error as e:
                    raise Exception(e) 
        elapsedtime = str(datetime.timedelta(seconds=(int(time.time()) - int(job[0][3]))))
        return ("sqlite3_dummy", elapsedtime, name + '/' + str(number) + '/' + jobid, None)

    def terminate(self, name, number, jobid, force=False, nodes=[]):
        """ terminates a job """
        # We cannot terminate a job that do not run.
        # We could add a specific entry in the DB to state if a job is terminated or not, but not worth it here.
        # Best way is just to answer that it was terminated (so return True),
        # so that Jarvice will automatically get its /exitstatus if we answer yes,
        # and the job will be garbage collected at this time.
        return True

    def online(self, host, status=True, comment=''):
        """ sets a node online or offline - legacy """
        return status

    def release(self, name, number, jobid):
        """ releases a held job """
        # We do not manage jobs held in this dummy code, lets just say "ok it was released"
        return True

    def events(self, name, number, jobid):
        """ returns list of events associated with job """
        # In normal time, we return here events for the job running
        # But nothing here for this dummy code, so lets just answer something generic
        return "This is events for job " + name + " \n Nothing to say, everything is ok."

    def request(self, path, qs):
        """ handle arbitrary request to the scheduler """

        # response helpers
        def rsp(code, content_type=None, content=None):
            return code, content_type, content

        def rsp_json(code, dct):
            return rsp(code, 'application/json', json.dumps(dct))

        # jobname and job ID are encoded in path, as we stated in /runstatus
        try:
            jobname, jobnum, jobid, method = path.lstrip('/').split('/')
        except Exception:
            try:
                jobname, jobnum, jobid = path.lstrip('/').split('/')
                method = ""
            except Exception:
                print('Path decode failed for ' + str(path))
                return rsp(400)

        # methods
        if method == 'ping':
            pass
        elif method == 'shutdown' or method == 'abort':
            self.terminate(jobname, None, jobid, force=(method == 'abort'))
        elif method == 'connect':
            pass
        elif method == 'info':
            # Interactive job, not supported in this dummy code
            readyjson = {'about': '', 'help': '', 'url': '', 'actions': {}}
            if self.jobs_are_interactive == 'True':
                readyjson['url'] = "http://localhost:8080"

            return rsp_json(200, readyjson)
        elif method == 'tail':
            # We should return plain text stdout of the job
            # Since there is nothing interesting happening here, lets answer a generic log
            stdout = """
Logs for job {name}
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur ac justo velit. Donec nec interdum lorem, in accumsan elit. Quisque sed felis eu risus suscipit semper. Donec purus velit, facilisis in neque eget, mollis semper eros. Curabitur pretium orci tempus interdum pretium. Nullam ultrices nulla arcu, in lacinia nibh luctus sit amet. Fusce nibh diam, iaculis ut sagittis vel, posuere at velit.

Pellentesque scelerisque nunc turpis, ac porta purus lobortis sit amet. Aliquam tincidunt sit amet ipsum ac finibus. Donec non enim non leo rhoncus auctor id vel metus. Class aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos himenaeos. Cras ligula lorem, condimentum scelerisque convallis sed, mattis quis odio. Aliquam tincidunt ullamcorper lorem, id lobortis diam varius at. Sed laoreet justo vel egestas pulvinar. Suspendisse quis nunc quis odio commodo suscipit. 
""".format(name=jobname)
            return rsp(200, content_type='text/plain',
                       content=stdout) if stdout else rsp(404)
        elif method == 'screenshot':
            # Interactive job, we return a screenshot in normal time
            rsp(404)

        # catch-all
        return rsp(200)
