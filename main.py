#!/usr/bin/env python3

from flask import Flask, request, jsonify
import json
import importlib
import os
import sys

app = Flask(__name__)

# Load the baremetal connector

baremetal = importlib.import_module(os.getenv('JARVICE_BAREMETAL_CONNECTOR'))
baremetal_connector = baremetal.baremetal_connector()

# ################## END POINTS - LEGACY


@app.route('/live')
def live():
    return jsonify({"status": "OK"}), 200


@app.route("/gc", methods=['GET'])
def gc():
    print('/gc')
    return_code = baremetal_connector.gc()
    if int(return_code) == 200:
        return jsonify({"status": "OK"}), 200
    else:
        return jsonify({"status": "BAD"}), 500


@app.route("/submit", methods=['POST'])
def submit():
    print('/submit')
    print(request.form)
    try:
        args = json.loads(request.form.get("args"))
        hpc_script = args['hpc_script']
        name = args["name"]
        number = args["number"]
        nodes = args["nodes"]
        bearer = args["bearer"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno)
        return "Could not load arguments, check your passed JSON data.", 500
    print('ok')
    try:
        return jsonify(
            baremetal_connector.submit(name, number, nodes, hpc_script, bearer)), 200
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e, exc_type, fname, exc_tb.tb_lineno)
        return "Could not load arguments, check your passed JSON data.", 500
#        return "Failed to submit job." + str(e), 500


@app.route("/nodes", methods=['GET'])
def nodes():
    print('/nodes')
    return "true", 200


@app.route("/running", methods=['GET'])
def running():
    print('/running')
    return jsonify(baremetal_connector.running()), 200


@app.route("/queued", methods=['GET'])
def queued():
    print('/queued')
    return jsonify(baremetal_connector.queued()), 200


@app.route("/exitstatus", methods=['POST'])
def exitstatus():
    print('/exitstatus')

    try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

    return jsonify(baremetal_connector.exitstatus(name, number, jobid)), 200


@app.route("/runstatus", methods=['POST'])
def runstatus():
    # Dropping rc, not needed for this downstream
    try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

    return jsonify(baremetal_connector.runstatus(name, number, jobid)), 200


@app.route("/terminate", methods=['POST'])
def terminate():
    # Dropping nodes and force, not needed for this downstream
    try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

    return jsonify(baremetal_connector.terminate(name, number, jobid)), 200


@app.route("/online", methods=['POST'])
def online():
    # Dropping comment, not needed for this downstream
    try:
        args = json.loads(request.form.get("args"))
        host = args["host"]
        status = args["status"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

    return jsonify(baremetal_connector.online(host, status)), 200


@app.route("/release", methods=['POST'])
def release():
    try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

    return jsonify(baremetal_connector.release(name, number, jobid)), 200


@app.route("/events", methods=['POST'])
def events():
    try:
        args = json.loads(request.form.get("args"))
        name = args["name"]
        number = args["number"]
        jobid = args["jobid"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

    return jsonify(baremetal_connector.events(name, number, jobid)), 200


@app.route('/request/<path:path>', methods=['POST'])
def requests(path):
    try:
        # print("-----------------------------------")
        # print(request.form)
        print("-----------------------------------")
        args = json.loads(request.form.get("args"))
        print(args)
        print("-----------------------------------")
        qs = args["qs"]
    except Exception as e:
        # In case of errors, these are often cryptique in this section
        # We want to pass a max of infos to ease debug.
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        return jsonify(
            (str(e) + '\n' + str(exc_type) + '\n' + str(fname) +
             '\n' + str(exc_tb.tb_lineno))), 400

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


# ## RUNNING SERVER

if __name__ == "__main__":
    #from waitress import serve

    print("Now running as server")
    print("URLs map:")
    print(app.url_map)

    #waitress_port = int(os.getenv('WAITRESS_PORT', "5000"))
    #waitress_bind_address = os.getenv('WAITRESS_BIND_ADDRESS', "0.0.0.0")

    #serve(app, host=waitress_bind_address, port=waitress_port)

    app.run(host="0.0.0.0", port=5000)
    quit()
