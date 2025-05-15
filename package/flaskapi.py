from .threads.faultTolerance import FaultTolerance
from .threads.apiThread import APIThread
from .threads.db import DB
from .classes.resources import Resources
from .classes.threadResources import ThreadResources
from flask import Blueprint, request, jsonify
from proxmoxer import ProxmoxAPI
from package import app
from dotenv import load_dotenv
import threading
import time
import os
from datetime import datetime, timedelta
from .models.vms import VM
from cryptography.fernet import Fernet
from . import db
import json

load_dotenv()

threads = []

main = Blueprint('main', __name__)

ip = os.getenv("PROXMOX_IP")
port = os.getenv("PROXMOX_PORT")
user = os.getenv("PROXMOX_USER")
password = os.getenv("PROXMOX_PASSWORD")

pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")

secretkey = os.getenv("ENCRYPT_KEY")

f = Fernet(secretkey.encode('utf-8'))   

proxmox = ProxmoxAPI(ip + ":"+ port, user=user, password=password, verify_ssl=False, timeout=30)
resources = Resources()


threading.Thread(target=APIThread, args=(proxmox, resources)).start()

while not resources.started:
    time.sleep(1)

with app.app_context():
    print("Starting fault tolerance")
    #startFaultTolerance()
    threading.Thread(target=DB, args=(proxmox, resources)).start()

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

    for vm in vmListDB:
        VM.query.filter_by(name=vm.name).delete()
        db.session.commit()
    
    for vm in vmListPost:
        new_vm = VM(name=vm)
        db.session.add(new_vm)
        db.session.commit()

    return {"status": "Fault tolerance completed"}, 200

@main.post("/rest/remotemigration")
def remote_migration():
    global proxmox
    global f
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
    
@main.post("/rest/remotemigration/gettoken")
def get_token():
    body = request.get_json()
    clienttoken = body['migration_token']
    clienttoken_bytes = bytes(clienttoken, 'utf-8')
    tokenDecrypted = f.decrypt(clienttoken_bytes).decode("utf-8")
    dataDecrypted = json.loads(tokenDecrypted)
    target_endpoint = dataDecrypted['target_endpoint']
    target_storage = dataDecrypted['target_storage']
    target_bridge = dataDecrypted['target_bridge']

    data = dict()
    data['target-endpoint'] = target_endpoint
    data['target-storage'] = target_storage
    data['target-bridge'] = target_bridge

    return jsonify(data), 200

@main.post("/rest/remotemigration/createtoken")
def create_token():
    global proxmox
    global f
    body = request.get_json()
    nodePost = body['node']
    ipaddr = body['ipaddress']
    target_storage = body['target_storage']
    target_bridge = body['target_bridge']

    fingerprint = ""

    nodesCluster = proxmox.cluster.config.join.get()["nodelist"]
    for node in nodesCluster:
        if node['name'] == nodePost:
            fingerprint = node['pve_fp']
            break

    date = datetime.now().today().strftime("%Y-%m-%d-%H-%M-%S")

    token = proxmox.access.users('root@pam').token("RemoteMigration-"+ date).post(
        expire=int((datetime.now() + timedelta(days=14)).timestamp()),
        privsep = 0
    )

    target_endpoint= f"apitoken=PVEAPIToken=root@pam!RemoteMigration-{date}={token['value']},host={ipaddr},fingerprint={fingerprint}"

    data = dict()
    data['target_endpoint'] = target_endpoint
    data['target_storage'] = target_storage
    data['target_bridge'] = target_bridge

    dataEncrypted = f.encrypt(json.dumps(data).encode('utf-8'))
    
    dataJson = dict()
    dataJson['migration_token'] = dataEncrypted.decode('utf-8')

    return jsonify(dataJson), 200

@main.get("/rest/test/")
def test():
    listStorage = []
    for storage in proxmox.cluster.resources.get(type="storage"):
        if storage['node'] == "pve1":
            listStorage.append(storage)
    return jsonify(listStorage), 200