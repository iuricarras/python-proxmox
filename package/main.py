from .fault_tolerance import fault_tolerance
from flask import Blueprint, request, jsonify
from proxmoxer import ProxmoxAPI
import threading
import time


class Resources:
    def __init__(self):
        self.nodes = []
        self.vms = []

main = Blueprint('main', __name__)

proxmox = ProxmoxAPI("192.168.0.10:8006", user="root@pam", password="ubuntu", verify_ssl=False, timeout=30)
resources = Resources()

def apiThread(proxmox, resources):
    while(True):
        try:
            resources.nodes = proxmox.nodes.get()
            resources.vms = proxmox.cluster.resources.get(type="vm")
            time.sleep(10)
        except Exception as e:
            print(f"Error connecting to Proxmox API: {e}")
            time.sleep(5)


threading.Thread(target=apiThread, args=(proxmox, resources)).start()

vmList = [ "qemu/100" , "qemu/101" ]

@main.get("/rest/faulttolerance")
def fault_tolerance_get():
    return jsonify(vmList), 200


@main.post("/rest/faulttolerance")
def fault_tolerance_post():
    global proxmox
    body = request.get_json()

    # Create and start threads
    threads = []

    vmList = body['vmList']
    if not vmList:
        return {"error": "No VMs provided"}, 400

    for i in vmList:
        thread = threading.Thread(target=fault_tolerance, args=(i, proxmox, resources))
        threads.append(thread)
        thread.start()

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

    

