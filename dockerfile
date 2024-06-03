# 기존 이미지 기반으로 설정 (예: python:3.8-slim)
FROM python:3.8-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY . /app

# 필요 라이브러리 설치
RUN pip install -r requirements.txt

# index.html 파일 복사
COPY index.html /app/templates/index.html

# Flask 서버 실행
CMD ["python", "app.py"]
