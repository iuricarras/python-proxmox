dbInfo = []
boot = True
threads = []
from package.models.vms import VM
from package.classes.threadResources import ThreadResources
from .faultTolerance import FaultTolerance
from package import app

import threading
import time

def DB(proxmox, resources):
    with app.app_context():
        global dbInfo
        global threads
        global boot
        while True:
            VMs = VM.query.all()
            print("VMs in DB: ", VMs)
            print("dbinfo: ", dbInfo)
            if boot:
                dbInfo = VMs
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
                boot = False
            else:
                dbaux = dbInfo.copy()
                for vm in VMs:
                    # Check if VM exists in the database
                    vm_exists = False
                    for vm_db in dbInfo:
                        if vm_db.name == vm.name:
                            print(f"VM {vm} already exists in the database.")
                            vm_exists = True
                            dbaux.remove(vm_db)
                            break
                    if not vm_exists:
                        # Start a new thread for the VM
                        thread_resources = ThreadResources()
                        thread_resources.vmID = vm.name
                        thread_resources.killThread = threading.Event()
                        thread = threading.Thread(target=FaultTolerance, args=(vm.name, proxmox, resources, thread_resources.killThread))
                        thread.start()
                        thread_resources.thread = thread
                        threads.append(thread_resources)
                        print(f"Thread started for VM {vm}")
                        dbInfo.append(vm)

                
                for vm in dbaux:
                    # If VM exists in the database but not in the request, stop the thread
                    for thread_resources in threads:
                        if thread_resources.vmID == vm.name:
                            thread_resources.killThread.set()
                            thread_resources.thread.join()
                            print(f"Thread for VM {vm.name} stopped.")
                            threads.remove(thread_resources)
                            dbInfo.remove(vm)
                            break
            time.sleep(5)