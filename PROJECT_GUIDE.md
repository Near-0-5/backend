# 📖 프로젝트 가이드

## 🛠️ 레포 클론 후 바로 실행
### 1) 가상환경 설정
1. uv 설치: `pip install uv`
2. 의존성 설치: `uv sync --no-install-project`

### 2) envs/.local.env 생성
```
mkdir envs
echo "SECRET_KEY=ozcodingschool0618$$JrCodingLab@^242321

DB_NAME=near05_db
DB_USER=db
DB_PASSWORD=pw1234
DB_HOST=db
DB_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

" >> envs/.local.env
```

### 3) githooks 경로 설정하기
> 깃에서 commit 메시지를 읽어 자동으로 지라 이슈넘버를 삽입해주는 파이프라인
1. .githooks를 git이 인식하도록 하는 명령어 : `git config core.hooksPath .githooks`
2. .githooks 내의 파일에 권한 부여 : `chmod +x .githooks/*`
3. .githooks가 등록이 됐는지 확인 : `git config --get core.hooksPath`

### 4) 도커 빌드
1. 서버 빌드/실행: `docker compose -f docker/docker-compose.local.yml up --build`
2. 컨테이너 목록 확인: `docker ps`
3. 로그 확인: `docker logs <컨테이너 이름>`

### 5) 마이그레이션


---

## 1. UV
<details>
<summary>설명</summary>

> Rust로 개발된 가상환경, 의존성 관리, python 버전 관리 도구.
- [참고자료 링크](https://devocean.sk.com/blog/techBoardDetail.do?ID=167420&boardType=techBlog)

- 설치: `pip install uv`

> ### UV 명령어
- 프로젝트 초기화: `uv init`

- 가상환경 생성: 자동 생성
- 가상환경 활성화: 자동 활성화
- 패키지 설치: `uv pip install <package>` or `uv add <package>`
- 의존성 기록: `uv lock`
- 의존성 설치: `uv sync`
- 패키지 실행: `uv run pytest`
- 개발환경 의존성 설치: `uv pip --dev <package>`
- 패키지 제거: `uv pip uninstall <package>` or `uv remove <package>`
- 패키지 업그레이드: `uv pip install --upgrade <package>`
- Python 버전 관리: `uv python install 3.13` and `uv run --python 3.11 script.py`
</details>

## 2. Pytest
<details>
<summary>설명</summary>

> 일단 알아서 찾아보슈
- [참고자료 링크]()


</details>





