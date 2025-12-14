<<<<<<< HEAD
# 1. 실행방법

1. 프로젝트 폴더로 이동

2. 가상환경 생성 (최초 1번)
```
python -m venv venv
```

3. 가상환경 켜기
- linux, Mac
```
source venv/bin/activate
```

- windows
```
# git bash
source venv/Scripts/activate

# PowerShell / CMD
.\venv\Scripts\activate
```

4. 라이브러리 설치
```
pip install -r requirements.txt
```

5. .env 파일 설정
- 루트 디렉토리에 생성

6. 실행
```
python -m uvicorn api.main:app --reload
```
