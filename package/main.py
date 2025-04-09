from .fault_tolerance import fault_tolerance
from flask import Blueprint, request
import threading




main = Blueprint('main', __name__)


@main.post("/rest/faulttolerance")
def fault_tolerance_route():
    
    body = request.get_json()
    vmList = body['vmList']

    # Create and start threads
    threads = []

    for i in vmList:
        thread = threading.Thread(target=fault_tolerance, args=(i,))
        threads.append(thread)
        thread.start()

    return {"status": "Fault tolerance completed"}, 200

    

