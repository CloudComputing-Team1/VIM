import os
import asyncio
from flask import Flask, request, Response
import requests
import re
from flask_cors import CORS

# Constants
HOST = '0.0.0.0'
PORT = 9999
VM_NAME = "Ubuntu22"
TEMPLATE_VM_NAME = "Ubuntu22_template"
CPU_USAGE_THRESHOLD = 80.0
READ_TIMEOUT = 10.0
MAX_CPU_USAGE_RECORDS = 5

# Global variables
cpu_usages = {}
connections = {}  # 연결된 모든 소켓 클라이언트 관리
client_id_pool = [True, True, True]  # 소켓 클라이언트에 할당할 번호 사용 가능 여부, True인 인덱스 + 1의 번호를 수여가능
message_queues = {}  # 클라이언트별 메시지 큐

async def monitor_vms():
    # VM 상태 모니터링 코드
    while True:
        if cpu_usages:
            min_cpu_usage_vm = get_min_cpu_usage_vm()
            # print(f"VM with minimum CPU usage: {min_cpu_usage_vm}")
            if get_average_cpu_usage(min_cpu_usage_vm) >= CPU_USAGE_THRESHOLD:
                auto_scale()

        await asyncio.sleep(1)

def get_average_cpu_usage(addr):
    # 주어진 주소에 대한 평균 CPU 사용량을 반환
    return sum(cpu_usages[addr]) / len(cpu_usages[addr]) if cpu_usages[addr] else 0

def get_min_cpu_usage_vm():
    # 최소 CPU 사용량을 가진 VM을 반환
    return min(cpu_usages, key=lambda addr: get_average_cpu_usage(addr))

def auto_scale():
    # 오토스케일링 로직 코드
    vm_id = find_first_true(client_id_pool)
    if vm_id != -1:
        print("Start VMM autoscaling!")
        clone_and_start_vm(TEMPLATE_VM_NAME, vm_id)

def find_first_true(bool_list):
    try:
        index = bool_list.index(True)
        return index
    except ValueError:
        return -1

async def handle_client(reader, writer):
    # 클라이언트 연결 및 CPU 사용량 보고를 처리
    addr = writer.get_extra_info('peername')
    print(f"Connected with {addr}")
    connections[addr] = {'reader': reader, 'writer': writer}
    cpu_usages[addr] = []
    message_queues[addr] = asyncio.Queue()

    index = find_first_true(client_id_pool)  # 사용가능한 부여번호를 탐색
    client_id_pool[index] = False
    
    # 처음 연결 시 클라이언트로 전송
    writer.write(f"Connection order: {index}".encode())
    await writer.drain()
    
    await asyncio.sleep(1)
    
    try:
        while True:
            message = "Check status"
            writer.write(message.encode())
            await writer.drain()
            # print(f"Sent: {message}")
            
            try:
                data = await asyncio.wait_for(reader.read(100), timeout=5.0)
            except asyncio.TimeoutError:
                print(f"No response from {addr}. Closing connection.")
                break

            if data:
                response = data.decode()
                print("response: ", response)
                if "CPU usage:" in response:
                    # CPU 사용량 문자열에서 숫자만 추출
                    try:
                        cpu_usage_value = float(response.split(': ')[1])
                    except (ValueError, IndexError) as e:
                        print(f"Error processing response from {addr}: {e}")
                        continue

                    # CPU 사용량을 리스트에 추가
                    cpu_usages[addr].append(cpu_usage_value)
                    # 5초 동안 평균 cpu 사용량을 계산할것임 auto-scaling의 기준점
                    if len(cpu_usages[addr]) > 5:
                        cpu_usages[addr].pop(0)  # 가장 오래된 데이터 삭제
                    average_usage = sum(cpu_usages[addr]) / len(cpu_usages[addr])
                    print(f"Average CPU usage for {addr}: {average_usage:.2f}%")
                    
                elif "Min CPU usage container port" in response:
                    match = re.search(r"Min CPU usage container port: (\d+), ports: dict_keys\((\[[^\]]+\])\)", response)
                    if match:
                        port = match.group(1)
                        keys_str = match.group(2)
                        keys_list = eval(keys_str)
                        await message_queues[addr].put([port] + keys_list)
                    
            else:
                print(f"Connection lost with {addr}. Closing connection.")
                break

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
    try:
        if 'CPU usage' in data:
            cpu_usage_value = float(data.split(': ')[1])
            return cpu_usage_value
    except (ValueError, IndexError) as e:
        print(f"Error processing response from {addr}: {e}")
        return None

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
        connections[addr]['writer'].close()
        del connections[addr]
    if addr in cpu_usages:
        del cpu_usages[addr]
    if addr in message_queues:
        del message_queues[addr]

async def send_message_to_specific_vm(ip, message):
    # 특정 VM에 연결되어 있다면 메시지를 보냅니다.
    if ip in connections:
        print(f"Sending message to {ip}")
        writer = connections[ip]['writer']

        # 메시지 보내기
        writer.write(message.encode())
        await writer.drain()

        # 응답 받기
        try:
            response = await asyncio.wait_for(message_queues[ip].get(), timeout=READ_TIMEOUT)
            if isinstance(response, list) and len(response) > 1:
                port = response[0]
                keys = response[1:]
                print(f"Received port: {port} and keys: {keys}")
                return port, keys
            else:
                print("Unexpected response format.")
                return None, None
        except asyncio.TimeoutError:
            print(f"No response from {ip}. Closing connection.")
            return None
        except Exception as e:
            print(f"Error communicating with {ip}: {e}")
            return None

        print(f"Response from {ip}: {port}")
        return port
    else:
        print(f"No active connection with {ip}")
        return None

async def main(host, port):
    # 서버와 모니터링 작업을 시작합니다. 
    server = await asyncio.start_server(handle_client, host, port)
    print(f'Serving on {host}:{port}')
    async with server:
        await asyncio.gather(
            server.serve_forever(),
            monitor_vms(),
            # monitor_containers(),
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

async def clone_and_start_vm(template_vm_name, vm_id):
    # 템플릿에서 VM을 복제하고 시작합니다.
    clone_cmd = f"VBoxManage.exe clonevm {template_vm_name} --name={VM_NAME}_{vm_id} --register --mode=all --options=keepallmacs --options=keepdisknames --options=keephwuuids"
    start_cmd = f"VBoxManage.exe startvm {VM_NAME}_{vm_id}"
    
    os.system(clone_cmd)
    os.system(start_cmd)
    # proc = await asyncio.create_subprocess_shell(clone_cmd)
    # await proc.communicate()  # Cloning finished

    # proc = await asyncio.create_subprocess_shell(start_cmd)
    # await proc.communicate()  # Starting finished

app = Flask(__name__)
CORS(app)

@app.after_request
def add_header(response):
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    min_cpu_usage_vm = get_min_cpu_usage_vm()
    
    container_port, ports = asyncio.run(send_message_to_specific_vm(min_cpu_usage_vm, "Get container with min CPU usage"))
    print("container_port: ", container_port)
    
    url = f'http://localhost:{container_port}/{path}'
    response = requests.request(
        method=request.method,
        url=url,
        headers={key: value for key, value in request.headers if key != 'Host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False)

    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for name, value in response.raw.headers.items()
               if name.lower() not in excluded_headers]

    response_content = response.content.decode('utf-8') + f"\n\nRequest was routed to VM with address: {min_cpu_usage_vm}"
    response = Response(response_content, response.status_code, headers)
    response = f"Container port: {container_port}, ports: {ports}"
    return response

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    start_vm(VM_NAME)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_flask)
    loop.run_until_complete(main(HOST, PORT))
