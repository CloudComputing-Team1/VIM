from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# VIM 및 VMM 정보 (예시)
vim_info = {
    "load_balancing_ip": "192.168.0.1",
    "auto_scaling_count": 3
}

vmm_info = {
    "load_balancing_ip": "192.168.0.2",
    "auto_scaling_count": 5
}

@app.route('/client_request', methods=['POST'])
def client_request():
    # 클라이언트 요청 헤더 설정
    headers = {
        "VIM": f"load balancing-vim#{vim_info['load_balancing_ip']}, auto scaling-vim#{vim_info['auto_scaling_count']}",
        "VMM": f"LB-vmm#{vmm_info['load_balancing_ip']}, auto scaling-docker#{vmm_info['auto_scaling_count']}"
    }
    
    # 실제 요청을 VIM 또는 VMM으로 포워딩 (예시 URL 사용)
    response = requests.post("http://target-service-url", headers=headers, data=request.data)
    
    # 응답 반환
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
