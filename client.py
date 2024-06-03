from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

VIM_IP = '127.0.0.1'  # VIM의 IP 주소
VIM_COUNT = 1  # 현재 존재하는 VIM의 갯수
DOCKER_CONTAINER_SERVER = 'http://localhost:5000'  # Docker 컨테이너 서버의 주소

@app.route('/client_request', methods=['POST'])
def handle_client_request():
    # 클라이언트의 요청을 받아서 처리합니다.
    client_data = request.get_json()

    # VIM의 IP 주소와 VIM의 갯수를 요청 헤더에 추가합니다.
    headers = {
        'VIM-IP': VIM_IP,
        'VIM-Count': str(VIM_COUNT),
    }

    # 요청을 Docker 컨테이너 서버로 전달합니다.
    response = requests.post(DOCKER_CONTAINER_SERVER, json=client_data, headers=headers)

    return jsonify(response.json()), response.status_code

if __name__ == '__main__':
    app.run(host='localhost', port=4000)