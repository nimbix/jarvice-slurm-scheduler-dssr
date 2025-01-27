# Dummy connector

This is a dummy connector that fake jobs runs.

When it receive a new job, job is stored into an SQLITE3 DB.
Job is set to fake queue, and after a specific time will be set to running.
After some time, job will be set as completed, and depending of the ratio set, will be tagged as Completed or in Error.

The following variables allow to adjust these settings:

* `JARVICE_DUMMY_JOB_RUNNING_TIME`: set running time in seconds. Default is 10.
* `JARVICE_DUMMY_JOB_QUEUED_TIME`: set queued time in seconds. Default is 5.
* `JARVICE_DUMMY_JOB_FAILING_PERCENT`: set failing percentage ration. 0 means all jobs will succeed, 100 means all will crash. Default is 50.
* `JARVICE_JOBS_ARE_INTERACTIVE`: make jobs interactive, and return a localhost url. Default is 'False'.