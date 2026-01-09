# 레포 받고 해야하는 설정들

## 1. uv 설치
- 설치 : `brew install uv`
- 의존성 설치 명령어 : `uv sync`
- 의존성 추가 명령어 : `uv add <package>`
- 의존성 삭제 명령어 : `uv remove <package>`

- 도커 빌드 : `docker compose -f docker-compose.local.yml up --build`

## 2. githooks 경로 설정하기
- .githooks를 git이 인식하도록 하는 명령어 : `git config core.hooksPath .githooks`
- .githooks 내의 파일에 권한 부여 : `chmod +x .githooks/*`
- .githooks가 등록이 됐는지 확인 : `git config --get core.hooksPath`

3. 