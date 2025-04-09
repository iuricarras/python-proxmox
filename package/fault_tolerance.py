import time
from proxmoxer import ProxmoxAPI

def fault_tolerance(vmID):
    vmHA= []
    nodeHA = []

    proxmox = ProxmoxAPI("192.168.0.10:8006", user="root@pam", password="ubuntu", verify_ssl=False, timeout=60)

    id = 1

    vms = proxmox.cluster.resources.get(type="vm")

    for vm in vms:
        if(vm['id'] == vmID):
            vmHA = vm

    # Get node information
    nodes = proxmox.nodes.get()
    # Print node names and status
    for node in nodes:
        if(node['node'] == vmHA['node']):
            nodeHA = node

    while nodeHA['status'] == 'online':

        if(id == 1):
            id = 0
        else:
            id = 1
            
        proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").delete()

        time.sleep(5)

        proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot.post(
            snapname=f"snapshot_ha_{id}",
            vmstate=1,
        )

        time.sleep(120)
        vms = proxmox.cluster.resources.get(type="vm")
        for vm in vms:
            if(vm['id'] == vmID):
                vmHA = vm

        # Get node information
        nodes = proxmox.nodes.get()
        # Print node names and status
        for node in nodes:
            if(node['node'] == vmHA['node']):
                nodeHA = node
        

        print(f"VM ID: {vmHA['id']}, Name: {vmHA['name']}, Status: {vmHA['status']}")
        print(f"Node Name: {nodeHA['node']}, Status: {nodeHA['status']}")

    print("E morreu...")


    vms = proxmox.cluster.resources.get(type="vm")
    for vm in vms:
        if(vm['id'] ==  vmID):
            vmHA = vm
            
    while vmHA['node'] == nodeHA['node']:
        time.sleep(10)
        print("Waiting for VM to migrate...")
        vms = proxmox.cluster.resources.get(type="vm")
        for vm in vms:
            if(vm['id'] ==  vmID):
                vmHA = vm
        

    if not proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").config.get()["snaptime"]:
        print("VM is in prepare state, not good...")
        proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").delete(
            force=1,
        )
        print("Snapshot deleted.")
        time.sleep(3)
        if(id == 1):
            id = 0
        else:
            id = 1

    proxmox.nodes(vmHA['node']).qemu(vmHA['id'].split('/')[1]).snapshot(f"snapshot_ha_{id}").rollback.post()
    print("Rollback completed.")

