from .threads.faultTolerance import FaultTolerance
from .threads.apiThread import APIThread
from .classes.resources import Resources
from .classes.threadResources import ThreadResources
from flask import Blueprint, request, jsonify
from proxmoxer import ProxmoxAPI
from package import app
from dotenv import load_dotenv
import threading
import time
import os
import requests
from .models.vms import VM
from . import db

load_dotenv()

threads = []

main = Blueprint('main', __name__)

ip = os.getenv("PROXMOX_IP")
port = os.getenv("PROXMOX_PORT")
user = os.getenv("PROXMOX_USER")
password = os.getenv("PROXMOX_PASSWORD")

pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")

proxmox = ProxmoxAPI(ip + ":"+ port, user=user, password=password, verify_ssl=False, timeout=30)
resources = Resources()

def startFaultTolerance():
    global threads
    VMs = VM.query.all()
    for vm in VMs:
        vmID = vm.name
        thread_resources = ThreadResources()
        thread_resources.vmID = vmID
        thread_resources.killThread = threading.Event()

        thread = threading.Thread(target=FaultTolerance, args=(vmID, proxmox, resources, thread_resources.killThread))
        thread.start()

        thread_resources.thread = thread

        threads.append(thread_resources)
        print(f"Thread started for VM {vmID}")


threading.Thread(target=APIThread, args=(proxmox, resources)).start()

while not resources.started:
    time.sleep(1)

with app.app_context():
    print("Starting fault tolerance")
    startFaultTolerance()


requests.post(
            f"https://api.pushover.net/1/messages.json",
            data={
                "token": pushover_token,
                "user": pushover_user,
                "message": f"Push notification from Proxmox API",
            },
        )

@main.get("/rest/faulttolerance")
def fault_tolerance_get():
    vmList = []
    vmListDB = VM.query.all()

    for vm in vmListDB:
        vmList.append(vm.name)

    return jsonify(vmList), 200


@main.post("/rest/faulttolerance")
def fault_tolerance_post():
    global threads

    vmListPost = request.get_json()
    vmListDB = VM.query.all()


    for vm in vmListPost:
        # Check if VM exists in the database
        vm_exists = False
        for vm_db in vmListDB:
            if vm_db.name == vm:
                vm_exists = True
                vmListDB.remove(vm_db)
                break
        if not vm_exists:
            # If VM does not exist, create a new entry in the database
            new_vm = VM(name=vm)
            db.session.add(new_vm)
            db.session.commit()
            print(f"VM {vm} added to the database.")

            # Start a new thread for the VM
            thread_resources = ThreadResources()
            thread_resources.vmID = vm
            thread_resources.killThread = threading.Event()
            thread = threading.Thread(target=FaultTolerance, args=(vm, proxmox, resources, thread_resources.killThread))
            thread.start()
            thread_resources.thread = thread
            threads.append(thread_resources)
            print(f"Thread started for VM {vm}")
        else:
            print(f"VM {vm} already exists in the database.")    

    
    for vm in vmListDB:
        # If VM exists in the database but not in the request, stop the thread
        for thread_resources in threads:
            if thread_resources.vmID == vm.name:
                thread_resources.killThread.set()
                print(f"Thread for VM {vm.name} stopped.")
                VM.query.filter_by(name=vm.name).delete()
                db.session.commit()
                break

    return {"status": "Fault tolerance completed"}, 200

@main.post("/rest/remotemigration")
def remote_migration():
    global proxmox
    body = request.get_json()
    vmID = body['vmID']
    node = body['node']
    target_endpoint = body['target_endpoint']
    target_storage = body['target_storage']
    target_bridge = body['target_bridge']

    data = dict()
    data['target-endpoint'] = target_endpoint
    data['target-storage'] = target_storage
    data['target-bridge'] = target_bridge

    try:
        proxmox.nodes(node).qemu(vmID).remote_migrate.post(
            **data
        )
        return {"status": "Remote migration completed"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

    

