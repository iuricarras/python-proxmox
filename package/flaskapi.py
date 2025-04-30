from .fault_tolerance import fault_tolerance
from flask import Blueprint, request, jsonify
from proxmoxer import ProxmoxAPI
from package import app
import threading
import time
from .models.vms import VM
from . import db

class Resources:
    def __init__(self):
        self.started = False
        self.nodes = []
        self.vms = []


class ThreadResources:
    def __init__(self):
        self.vmID = ""
        self.thread = None
        self.killThread = None


threads = []

main = Blueprint('main', __name__)

proxmox = ProxmoxAPI("192.168.0.10:8006", user="root@pam", password="ubuntu", verify_ssl=False, timeout=30)
resources = Resources()

def apiThread(proxmox, resources):
    print("Starting API thread")
    while(True):
        try:
            resources.nodes = proxmox.nodes.get()
            resources.vms = proxmox.cluster.resources.get(type="vm")
            if not resources.started:
                resources.started = True
                print("Proxmox API connection established and resources fetched.")
            time.sleep(10)
        except Exception as e:
            print(f"Error connecting to Proxmox API: {e}")
            time.sleep(5)


def startFaultTolerance():
    global threads
    global proxmox
    global resources
    VMs = VM.query.all()
    for vm in VMs:
        vmID = vm.name
        thread_resources = ThreadResources()
        thread_resources.vmID = vmID
        thread_resources.killThread = threading.Event()

        thread = threading.Thread(target=fault_tolerance, args=(vmID, proxmox, resources, thread_resources.killThread))
        thread.start()

        thread_resources.thread = thread

        threads.append(thread_resources)
        print(f"Thread started for VM {vmID}")




threading.Thread(target=apiThread, args=(proxmox, resources)).start()

while not resources.started:
    time.sleep(1)

with app.app_context():
    print("Starting fault tolerance")
    startFaultTolerance()



@main.get("/rest/faulttolerance")
def fault_tolerance_get():
    vmList = []
    vmListDB = VM.query.all()

    for vm in vmListDB:
        vmList.append(vm.name)

    return jsonify(vmList), 200


@main.post("/rest/faulttolerance")
def fault_tolerance_post():
    global proxmox
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
            thread = threading.Thread(target=fault_tolerance, args=(vm, proxmox, resources, thread_resources.killThread))
            thread.start()
            thread_resources.thread = thread
            threads.append(thread_resources)
            print(f"Thread started for VM {vm}")
        else:
            print(f"VM {vm} already exists in the database.")    


        #new_vm = VM(name=vm)

        #db.session.add(new_vm)
        #db.session.commit()
    
    for vm in vmListDB:
        # If VM exists in the database but not in the request, stop the thread
        for thread_resources in threads:
            if thread_resources.vmID == vm.name:
                thread_resources.killThread.set()
                print(f"Thread for VM {vm.name} stopped.")
                VM.query.filter_by(name=vm.name).delete()
                db.session.commit()
                break

#    for i in vmList:
#        thread = threading.Thread(target=fault_tolerance, args=(i, proxmox, resources))
#        threads.append(thread)
#        thread.start()

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

    

