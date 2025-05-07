import time
from dotenv import load_dotenv
import os
import requests


def FaultTolerance(vmID, proxmox, resources, killThread):

    load_dotenv()

    pushover_token = os.getenv("PUSHOVER_TOKEN")
    pushover_user = os.getenv("PUSHOVER_USER")

    vmHA= []
    nodeHA = []

    id = 1

    vms = resources.vms

    for vm in vms:
        if(vm['id'] == vmID):
            vmHA = vm

    # Get node information
    nodes = resources.nodes
    # Print node names and status
    for node in nodes:
        if(node['node'] == vmHA['node']):
            nodeHA = node

    while not killThread.is_set() and nodeHA['status'] == 'online':

        if(id == 1):
            id = 0
        else:
            id = 1
        
        try:
            proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").delete()
            time.sleep(5)
            proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot.post(
                snapname=f"snapshot_ha_{id}",
                vmstate=1,
            )
            print(f"[{vmID}] - Snapshot created.")
            time.sleep(60)
        except Exception as e:
            print(f"[{vmID}] - Error managing snapshot: {e}")
            time.sleep(10)
            if(id == 1):
                id = 0
            else:
                id = 1

  
        vms = resources.vms
        for vm in vms:
            if(vm['id'] == vmID):
                vmHA = vm

        # Get node information
        nodes = resources.nodes
        # Print node names and status
        for node in nodes:
            if(node['node'] == vmHA['node']):
                nodeHA = node
        

        print(f"VM ID: {vmHA['id']}, Name: {vmHA['name']}, Status: {vmHA['status']}")
        print(f"Node Name: {nodeHA['node']}, Status: {nodeHA['status']}")

    if killThread.is_set():
        print(f"[{vmID}] - Thread killed.")
        return

    print(f"[{vmID}] - Node is offline, starting migrating...")
    requests.post(
            f"https://api.pushover.net/1/messages.json",
            data={
                "token": pushover_token,
                "user": pushover_user,
                "title": f"Fault Tolerance - Node {nodeHA['node']} offline - VM {vmID}",
                "message": f"[{vmID}] - Node is offline. Starting migrating to another node.",
            },
        )

    vms = resources.vms
    for vm in vms:
        if(vm['id'] ==  vmID):
            vmHA = vm
    
    originalNode = ''

    nodes = resources.nodes
        # Print node names and status
    for node in nodes:
        if(node['node'] == vmHA['node']):
            originalNode = node

    while vmHA['node'] == nodeHA['node'] and originalNode['status'] != 'running':
        time.sleep(10)
        print(f"[{vmID}] - Waiting for VM to migrate...")
        vms = resources.vms
        for vm in vms:
            if(vm['id'] ==  vmID):
                vmHA = vm
                
        nodes = resources.nodes
        # Print node names and status
        for node in nodes:
            if(node['node'] == vmHA['node']):
                originalNode = node

        

    if not proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").config.get()["snaptime"]:
        print(f"[{vmID}] - VM is in prepare state, not good...")
        proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").delete(
            force=1,
        )
        print(f"[{vmID}] - Snapshot deleted.")
        time.sleep(3)
        if(id == 1):
            id = 0
        else:
            id = 1

    proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").rollback.post()
    print(f"[{vmID}] - Rollback completed.")
    requests.post(
            f"https://api.pushover.net/1/messages.json",
            data={
                "token": pushover_token,
                "user": pushover_user,
                "title": f"Fault Tolerance - Rollback - VM {vmID}",
                "message": f"[{vmID}] - Vm assigned to node {vmHA['node']} - Rollback completed.",
            },
        )

