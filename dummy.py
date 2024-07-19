import sqlite3
import os
import time
from contextlib import closing

class baremetal_connector(object):



    def __init__(self):
        # Max job time in second
        self.job_time = int(os.getenv('JARVICE_DUMMY_JOB_TIME', '60'))
        # Percent of failing jobs (random with probability based on this ratio)
        self.job_failing_ratio = int(os.getenv('JARVICE_DUMMY_JOB_FAILING_RATIO', '0'))

        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute("CREATE TABLE IF NOT EXISTS job (name TEXT, number INTEGER, jobid TEXT, starttime INTEGER)")

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
        with closing(sqlite3.connect("jobs.db")) as connection:
            with closing(connection.cursor()) as cursor:
                try:
                    entry = "INSERT INTO job VALUES " + str((name, str(number), "dummy_" + str(number), str(int(time.time()))))
                    cursor.execute(entry)
                    connection.commit()
                except sqlite3.Error as e:
                    raise Exception(e) 
                return "dummy_" + str(number), entry
