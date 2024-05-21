import os
import asyncio

cpu_usages = {}
connections = {}  # 연결된 모든 클라이언트 관리

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Connected with {addr}")
    connections[addr] = writer
    cpu_usages[addr] = []  # 각 클라이언트별 CPU 사용량 리스트 초기화

    try:
        while True:
            message = "Check status"
            writer.write(message.encode())
            await writer.drain()
            print(f"Sent: {message}")

            try:
                data = await asyncio.wait_for(reader.read(100), timeout=5.0)
            except asyncio.TimeoutError:
                print(f"No response from {addr}. Closing connection.")
                break

            if data:
                response = data.decode()
                print(f"Received: {response} from {addr}")

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
            else:
                print(f"Connection lost with {addr}. Closing connection.")
                break

            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error with {addr}: {e}")

    print("Closing the connection")
    writer.close()
    if addr in connections:
        del connections[addr]  # 연결 제거
    if addr in cpu_usages:
        del cpu_usages[addr]  # CPU 사용 정보 삭제

async def send_message_to_specific_vm(ip, message):
    if ip in connections:
        print(f"Sending message to {ip}")
        writer = connections[ip]
        writer.write(message.encode())
        await writer.drain()
    else:
        print(f"No active connection with {ip}")

async def main(host, port):
    server = await asyncio.start_server(handle_client, host, port)
    print(f'Serving on {host}:{port}')
    async with server:
        await server.serve_forever()
        
def is_vm_running(vm_name):
    # 실행 중인 VM 목록을 확인
    output = os.popen("VBoxManage list runningvms").read()
    
    # 결과를 확인하여 지정된 VM 이름이 포함되어 있는지 검사
    if vm_name in output:
        return True
    return False

# 서버 호스트와 포트 설정
HOST = '0.0.0.0'
PORT = 9999

# 첫 서비스 서버(VM) 오픈
vm_name = "Ubuntu22"
template_vm_name = "Ubuntu22_template"
if is_vm_running(vm_name):
    print(f"Already started vm {vm_name}")
else:
    print(f"Start vm {vm_name}")
    os.system(f"VBoxManage.exe startvm {vm_name}")

os.system("VBoxManage.exe clonevm " + template_vm_name + " --name=" + vm_name + "_1" + " --register --mode=all --options=keepallmacs --options=keepdisknames --options=keephwuuids")
os.system("VBoxManage.exe startvm " + vm_name + "_1")

# 이벤트 루프 시작s
asyncio.run(main(HOST, PORT))
