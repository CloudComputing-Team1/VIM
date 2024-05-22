import os
import asyncio
import docker

# Constants
HOST = '0.0.0.0'
PORT = 9999
VM_NAME = "Ubuntu22"
TEMPLATE_VM_NAME = "Ubuntu22_template"
CPU_USAGE_THRESHOLD = 70.0
READ_TIMEOUT = 5.0
MAX_CPU_USAGE_RECORDS = 5

# Global variables
cpu_usages = {}
connections = {}  # 연결된 모든 클라이언트 관리

async def monitor_vms():
    # VM 상태 모니터링 코드
    while True:
        for addr, writer in connections.items():
            message = "Check status"
            writer.write(message.encode())
            await writer.drain()
            print(f"Sent: {message} to {addr}")
        await asyncio.sleep(1)

async def monitor_containers():
    # Docker 컨테이너 상태 모니터링 코드
    client = docker.from_env()
    while True:
        for container in client.containers.list():
            print(f"Container {container.id} is {container.status}")
        await asyncio.sleep(1)

def get_min_cpu_usage_vm():
    # 최소 CPU 사용량을 가진 VM을 반환
    return min(cpu_usages, key=cpu_usages.get)

def auto_scale():
    # 오토스케일링 로직 코드
    for addr, usages in cpu_usages.items():
        average_usage = sum(usages) / len(usages)
        if average_usage > CPU_USAGE_THRESHOLD:
            print(f"High CPU usage on {addr}. Starting new VM.")
            os.system(f"VBoxManage.exe clonevm {TEMPLATE_VM_NAME} --name={VM_NAME}_1 --register --mode=all --options=keepallmacs --options=keepdisknames --options=keephwuuids")
            os.system(f"VBoxManage.exe startvm {VM_NAME}_1")


async def handle_client(reader, writer):
    # 클라이언트 연결 및 CPU 사용량 보고를 처리
    addr = writer.get_extra_info('peername')
    print(f"Connected with {addr}")
    connections[addr] = writer
    cpu_usages[addr] = []

    try:
        while True:
            message = "Check status"
            writer.write(message.encode())
            await writer.drain()
            print(f"Sent: {message}")

            data = await read_data(reader, addr)
            if data is None:
                break

            cpu_usage_value = process_data(data, addr)
            if cpu_usage_value is not None:
                update_cpu_usage(addr, cpu_usage_value)

            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error with {addr}: {e}")

    close_connection(addr)

async def read_data(reader, addr):
    # 클라이언트로부터 데이터를 타임아웃과 함께 읽어옵니다.
    try:
        data = await asyncio.wait_for(reader.read(100), timeout=READ_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"No response from {addr}. Closing connection.")
        return None
    return data

def process_data(data, addr):
    # 받은 데이터를 처리하고 CPU 사용량 값을 반환합니다.
    response = data.decode()
    print(f"Received: {response} from {addr}")

    try:
        cpu_usage_value = float(response.split(': ')[1])
    except (ValueError, IndexError) as e:
        print(f"Error processing response from {addr}: {e}")
        return None

    return cpu_usage_value

def update_cpu_usage(addr, cpu_usage_value):
    # 주어진 주소에 대한 CPU 사용량 기록을 업데이트합니다.
    cpu_usages[addr].append(cpu_usage_value)
    if len(cpu_usages[addr]) > MAX_CPU_USAGE_RECORDS:
        cpu_usages[addr].pop(0)
    average_usage = sum(cpu_usages[addr]) / len(cpu_usages[addr])
    print(f"Average CPU usage for {addr}: {average_usage:.2f}%")


def close_connection(addr):
    # 클라이언트와의 연결을 닫고 레코드에서 제거합니다.
    print("Closing the connection")
    if addr in connections:
        connections[addr].close()
        del connections[addr]
    if addr in cpu_usages:
        del cpu_usages[addr]

async def send_message_to_specific_vm(ip, message):
    # 특정 VM에 연결되어 있다면 메시지를 보냅니다.
    if ip in connections:
        print(f"Sending message to {ip}")
        writer = connections[ip]
        writer.write(message.encode())
        await writer.drain()
    else:
        print(f"No active connection with {ip}")


async def main(host, port):
    # 서버와 모니터링 작업을 시작합니다.
    server = await asyncio.start_server(handle_client, host, port)
    print(f'Serving on {host}:{port}')
    async with server:
        await asyncio.gather(
            server.serve_forever(),
            monitor_vms(),
            monitor_containers(),
        )

def is_vm_running(vm_name):
    # VM이 실행 중인지 확인합니다.
    output = os.popen("VBoxManage list runningvms").read()
    return vm_name in output

def start_vm(vm_name):
    # VM이 이미 실행 중이지 않은 경우 VM을 시작합니다.
    if is_vm_running(vm_name):
        print(f"Already started vm {vm_name}")
    else:
        print(f"Start vm {vm_name}")
        os.system(f"VBoxManage.exe startvm {vm_name}")

def clone_and_start_vm(template_vm_name, vm_name):
    # 템플릿에서 VM을 복제하고 시작합니다.
    os.system(f"VBoxManage.exe clonevm {template_vm_name} --name={vm_name}_1 --register --mode=all --options=keepallmacs --options=keepdisknames --options=keephwuuids")
    os.system(f"VBoxManage.exe startvm {vm_name}_1")

if __name__ == "__main__":
    start_vm(VM_NAME)
    clone_and_start_vm(TEMPLATE_VM_NAME, VM_NAME)
    asyncio.run(main(HOST, PORT))