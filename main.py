#!/usr/bin/env python3
#
# NIMBIX OSS
# ----------
#
# Copyright (c) 2024 Nimbix, Inc.
#

from flask import Flask, request, jsonify
import json
import importlib
import os
import sys

app = Flask(__name__)

# Load the baremetal connector

baremetal = importlib.import_module(os.getenv('JARVICE_BAREMETAL_CONNECTOR'))
baremetal_connector = baremetal.baremetal_connector()

# Make verbose answers in case of crash, its simpler for debug
def report_error(e):
     exc_type, exc_obj, exc_tb = sys.exc_info()
     fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
     print(e, exc_type, fname, exc_tb.tb_lineno)
     return str(e) + str(exc_type) + str(fname) + str(exc_tb.tb_lineno)


# ################## END POINTS - LEGACY


# /live
# Used to check if downstream is available
# Returns as json
# - {"status": "OK"}, 200
@app.route('/live')
def live():
    return jsonify({"status": "OK"}), 200


# /gc
# garbage collection endpoint; fail if cluster not reachable
# Returns as json
# - {"status": "OK"}, 200 if cluster is available
# - {"status": "BAD"}, 500 if cluster is not available
@app.route("/gc", methods=['GET'])
def gc():
    return_code = baremetal_connector.gc()
    if int(return_code) == 200:
        return jsonify({"status": "OK"}), 200
    else:
        return jsonify({"status": "BAD"}), 500


# /submit
# submit a new job to target cluster
# We receive name of the job, number of the job, nb of nodes to allocate to the job, a bearer token (optional) and the hpc_script to execute.
# Returns as json
# - jobid, fscript 200 if job was submitted properly. Jobid is the cluster local job number (for example id returned by slurm sbatch command), and fscript is in theory the content of the script executed by the job, but can be empty if not needed.
# - 500 if something failed
@app.route("/submit", methods=['POST'])
def submit():
    # try:
        args = json.loads(request.form.get("args"))
        hpc_script = args['hpc_script']
        name = args["name"]
        number = args["number"]
        nodes = args["nodes"]
        bearer = args["bearer"]
        print(args)
        print(bearer)
        return jsonify(
            baremetal_connector.submit(name, number, nodes, hpc_script, bearer)), 200
    # except Exception as e:
    #     print(report_error(e))
    #     return jsonify(report_error(e)), 500


# /nodes
# K8S specific, only returns true here
@app.route("/nodes", methods=['GET'])
def nodes():
    return "true", 200


# /running
# send to upstream the list of jobids running
# Example : 
# - [(name, jobid), ...], 200 if ok, can even be an empty list [], 200 if no jobs are running
# - 500 if something failed
@app.route("/running", methods=['GET'])
def running():
    # try:
        return jsonify(baremetal_connector.running()), 200
    # except Exception as e:
    #     return report_error(e), 500


# /queued
# send to upstream the list of jobids queued
# same concept than /running
# Example : 
# - [(name, jobid), ...], 200 if ok, can even be an empty list [], 200 if no jobs are queued
# - 500 if something failed
@app.route("/queued", methods=['GET'])
def queued():
    print('/queued')
    return jsonify(baremetal_connector.queued()), 200


# /exitstatus
# returns exit status of a completed job, along with the total time of the job, and the final logs of the job
# returns:
# - exitcode, totaltime, logs, 200 if ok
# - 500 if something failed
# Note that:
#   exitcode:
#     - 1 means failed somehow
#     - -15 means canceled somehow
#     - 0 means completed ok
#     - -9 for anything else, means canceled but we do not know why
#   totaltime is in format 'hh:mm:ss', so for example 01:22:13, as a string
#   logs is a list of 2 items:
#      [0] contains the stdout of the job
#      [1] contains the termination state
# Important: gc_job (aka cleaning of job files, etc.) must be done at this stage, so existatus MUST garbage collect the job
@app.route("/exitstatus", methods=['POST'])
def exitstatus():
        print('/exitstatus')

    # try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
        return jsonify(baremetal_connector.exitstatus(name, number, jobid)), 200
    # except Exception as e:
    #     return report_error(e), 500


# /runstatus
# returns running status of a single job
# returns is a tupple if ok:
# - (nodes, elapsed, name + '/' + str(number) + '/' + jobid, None), 200 if ok
# - 500 if not ok
# It is important to understand returned values:
# nodes is the list of nodes the job is running on, not very important, can be dummy
# elapsed is the time elapsed of the job, same format than for /existatus
# third element is the path to be used when quering /request endpoint later, most of the time "name + '/' + str(number) + '/' + jobid" is perfect
# last element is none for our usage
@app.route("/runstatus", methods=['POST'])
def runstatus():
    # Dropping rc, not needed for this downstream
    # try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
        return jsonify(baremetal_connector.runstatus(name, number, jobid)), 200
    # except Exception as e:
    #     return report_error(e), 500


# /terminate
# terminate a job, aka kill it
# note that garbage collect is not done here, but at /exitstatus
@app.route("/terminate", methods=['POST'])
def terminate():
    # Dropping nodes and force, not needed for this downstream
    # try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
        return jsonify(baremetal_connector.terminate(name, number, jobid)), 200
    # except Exception as e:
    #     return report_error(e), 500


# /online
# K8S only, returns True, 200 here
@app.route("/online", methods=['POST'])
def online():
    return jsonify(True), 200


# /release
# Release an held job
# not all schedulers are able to do that
# returns True, 200 if ok
@app.route("/release", methods=['POST'])
def release():
    # try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
        return jsonify(baremetal_connector.release(name, number, jobid)), 200
    # except Exception as e:
    #     return report_error(e), 500


# /events
# Grab job events if any
# returns events, 200 with events being some stdout of the events call
@app.route("/events", methods=['POST'])
def events():
    # try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
        return jsonify(baremetal_connector.events(name, number, jobid)), 200
    # except Exception as e:
    #     return report_error(e), 500



# /request/XXXX
# This is an important endpoint, as it is used to communicate with the running job
# Call path, if set as "name + '/' + str(number) + '/' + jobid" in /runstatus will be of format:
# /request/name/number/jobid/method with method being the actual request
# method can be ping, shutdown, abort, info, tail, etc.
# Answer depends of method requested. All should answer in json, expect tail that answer in plaintext format

@app.route('/request/<path:path>', methods=['POST'])
def requests(path):
    # try:
        # print("-----------------------------------")
        # print(request.form)
        print("-----------------------------------")
        args = json.loads(request.form.get("args"))
        print(args)
        print("-----------------------------------")
        qs = args["qs"]

        # This method is not "standard"
        # as it can return raw content or json based content
        code, content_type, content = baremetal_connector.request(path, qs)
        print(code)
        print(content_type)
        print(content)
        if content_type == 'application/json':
            ret = json.loads(content)
            return jsonify(ret)
        else:
            if content is None:
                return "", code
            else:
                return content, code
    # except Exception as e:
    #     return report_error(e), 500


# ## RUNNING SERVER

if __name__ == "__main__":
#    from waitress import serve

    print("Now running as server")
    print("URLs map:")
    print(app.url_map)

 #   waitress_port = int(os.getenv('WAITRESS_PORT', "5000"))
 #   waitress_bind_address = os.getenv('WAITRESS_BIND_ADDRESS', "0.0.0.0")

 #   serve(app, host=waitress_bind_address, port=waitress_port)

    app.run(host="0.0.0.0", port=5000, debug=True)
    quit()
