
# 📽️ Near0.5 - 실시간 스트리밍 서비스
<br>

---
<div align=center> 

### 🔗 <a href="https://near-0-5.vercel.app/" target="_blank"> Near0.5 스트리밍 사이트 바로가기</a>
</div>

---

<br>

## 📖 프로젝트 소개

>  본 프로젝트(Near0.5)는 FastAPI와 AWS IVS를 기반으로 한 __```실시간 스트리밍 서비스```__ 입니다. 멀게만 느껴지던 스타의 공연을 __1열보다 더 가까이__, __당신의 곁에__ 제공하는 것을 목표로 합니다.

<br>

## 🗓️ 프로젝트 기간
- 2025년 1월 5일 - 2026년 2월 9일
<br>


## 🧰 사용 스택



<div align=center> 
<img src="https://img.shields.io/badge/Python_3.13-3776AB?style=for-the-badge&logo=python&logoColor=white">
<img src="https://img.shields.io/badge/fastapi-009688?style=for-the-badge&logo=fastapi&logoColor=white">
<img src="https://img.shields.io/badge/tortoiseorm-2C3E50?style=for-the-badge">
<img src="https://img.shields.io/badge/postgresql-316192?style=for-the-badge&logo=postgresql&logoColor=white">
<img src="https://img.shields.io/badge/redis-DC382D?style=for-the-badge&logo=redis&logoColor=white">
<img src="https://img.shields.io/badge/celery-37814A?style=for-the-badge&logo=celery&logoColor=white">
<img src="https://img.shields.io/badge/Amazon_IVS-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white">
<img src="https://img.shields.io/badge/Amazon_Cognito-FF9900?style=for-the-badge&logo=amazoncognito&logoColor=white">
<img src="https://img.shields.io/badge/Amazon_S3-569A31?style=for-the-badge&logo=amazons3&logoColor=white">
<img src="https://img.shields.io/badge/Amazon_EventBridge-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white">

  <br>
</div>
  <br>
  <br>

---


## 🖥️ 서비스 소개

- 자세한 사항이 궁금하다면 <a href="https://www.miricanvas.com/v2/design2/v/89ff855c-3708-4271-952f-c0904e44c75c" target="_blank"> 발표 자료 </a> 를 참고하세요.



### ` 유저 `

> AWS Cognito를 이용한 소셜로그인 제공


<details> <summary><strong>👀 사용자 기능 (User) </strong></summary>

- 뭐라도
- 적어주세요

</details>

<details>
<summary><strong>🛠 관리자 기능 (Admin)</strong></summary>

- 뭐라도
- 적어주세요
</details>

---
### ` 스트리밍 `

> AWS IVS 기반 콘서트 라이브 스트리밍, 녹화 영상 제공


<details> <summary><strong>👀 사용자 기능 (User) </strong></summary>

- 뭐라도
- 적어주세요

</details>

<details>
<summary><strong>🛠 관리자 기능 (Admin)</strong></summary>

- 뭐라도
- 적어주세요
</details>


<br>



---

### ` 실시간 채팅 `

> WebSocket 기반 실시간 채팅 (Redis Pub/Sub)



<details> <summary><strong>👀 사용자 기능 (User) </strong></summary>

- 뭐라도
- 적어주세요
</details>

<details>
<summary><strong>🛠 관리자 기능 (Admin)</strong></summary>

- 뭐라도
- 적어주세요

</details>

---

### ` 아티스트 `

> 이건 뭔 설명을 적어야하나


<details> <summary><strong>👀 사용자 기능 (User) </strong></summary>

- 뭐라도
- 적어주세요

</details>

<details>
<summary><strong>🛠 관리자 기능 (Admin)</strong></summary>

- 뭐라도
- 적어주세요
</details>

---


### ` 알림 `

> 스트리밍 이벤트 알림 (Celery)


<details> <summary><strong>👀 사용자 기능 (User) </strong></summary>

- 뭐라도
- 적어주세요
</details>

<details>
<summary><strong>🛠 관리자 기능 (Admin)</strong></summary>

- 뭐라도
- 적어주세요

</details>


## 🗂 프로젝트 구조

```
.
├── PROJECT_GUIDE.md                # 프로젝트 설계 / 아키텍처 문서
├── README.md
├── app
│   ├── __init__.py
│   ├── admin                       # FastAdmin 관련 설정
│   │   ├── __init__.py
│   │   ├── app.py                  # Admin 앱 초기화
│   │   ├── models.py               # Admin에서 사용하는 ORM 모델 정의
│   │   ├── resources.py            # Admin 리소스 설정
│   │   └── templates/              # Admin 커스텀 템플릿
│   │     
│   ├── api                         
│   │   ├── __init__.py
│   │   ├── deps.py                 # 공용 의존성
│   │   ├── errors.py               # 전역 에러 처리
│   │   └── router.py               # 도메인 라우터 통합
│   ├── core
│   │   ├── __init__.py
│   │   ├── config.py               # 환경변수 및 설정 관리
│   │   ├── logging.py              # 로깅 설정
│   │   ├── pagination.py           # 커서 기반 페이지네이션
│   │   ├── redis.py                # Redis 연결 설정
│   │   ├── security.py             # JWT/보안 관련 로직
│   │   ├── tortoise_config.py      # Tortoise ORM 설정
│   │   └── utils
│   │       ├── __init__.py
│   │       ├── image_resizer.py    # 이미지 리사이징 및 S3 업로드
│   │       └── permissions.py      # 권한 체크 유틸
│   ├── domains
│   │   ├── __init__.py
│   │   ├── artists                 # 아티스트 관리
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # ORM 모델
│   │   │   ├── router.py           # API 엔드포인트
│   │   │   ├── schemas.py          # Pydantic 스키마
│   │   │   └── service.py          # 비즈니스 로직
│   │   │  
│   │   ├── auth                    # 인증/로그인
│   │   │   ├── __init__.py          
│   │   │   ├── router.py           . 
│   │   │   ├── schemas.py          . 
│   │   │   └── service.py          . 
│   │   │  
│   │   ├── chat                    # 실시간 채팅 (WebSocket)
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # 커넥션 매니저
│   │   │   ├── repository.py       # Redis 메시지 저장/조회
│   │   │   ├── router_ws.py        # WebSocket 엔드포인트
│   │   │   ├── schemas.py          . 
│   │   │   └── service.py          . 
│   │   │  
│   │   ├── concerts                # 콘서트
│   │   │   ├── __init__.py
│   │   │   ├── deps.py             # 권한/검증 의존성
│   │   │   ├── models.py           . 
│   │   │   ├── router.py           . 
│   │   │   ├── schemas.py          . 
│   │   │   └── service.py          . 
│   │   │  
│   │   ├── notifications           # 알림 시스템
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          . 
│   │   │   ├── models.py           . 
│   │   │   ├── router.py           . 
│   │   │   ├── schemas.py          . 
│   │   │   ├── service.py          . 
│   │   │   └── tasks.py            # Celery 비동기 알림 작업
│   │   │  
│   │   ├── streams                 # 스트리밍
│   │   │   ├── __init__.py
│   │   │   ├── admin               # 관리자용 스트림 관리
│   │   │   │   ├── __init__.py     .
│   │   │   │   ├── ivs_webhook_router.py   # IVS 상태 웹훅
│   │   │   │   ├── router.py       . 
│   │   │   │   ├── schemas.py      . 
│   │   │   │   └── service.py      . 
│   │   │   ├── client              # 사용자용 스트림 조회
│   │   │   │   ├── __init__.py     . 
│   │   │   │   ├── router.py       . 
│   │   │   │   ├── schemas.py      . 
│   │   │   │   └── service.py      . 
│   │   │   ├── deps.py             # 스트림 권한 의존성
│   │   │   ├── models.py           . 
│   │   │   └── permissions.py      . 
│   │   │  
│   │   └── users                   # 사용자 관리
│   │       ├── __init__.py
│   │       ├── models.py           . 
│   │       ├── router.py           . 
│   │       ├── schemas.py          . 
│   │       └── service.py          . 
│   │   
│   ├── integrations                # 외부 서비스 연동
│   │   ├── __init__.py
│   │   ├── aws_ivs                 # AWS IVS 클라이언트
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # IVS API 호출
│   │   │   └── playback.py         # playback URL 처리
│   │   ├── kakao.py                # 카카오 로그인 연동
│   │   ├── naver.py                # 네이버 로그인 연동
│   │   └── s3_client.py            # S3 업로드/삭제
│   ├── main.py                     
│   └── tasks                       # Celery 설정
│       ├── __init__.py
│       ├── beat_schedule.py        # 스케줄 작업
│       └── celery_app.py           # Celery 앱 초기화
│   
├── docker                          # 도커 설정
│   ├── Dockerfile.dev              .
│   ├── Dockerfile.prod             .
│   ├── docker-compose.dev.yml      .
│   └── docker-compose.prod.yml     .
│   
├── infra                           # 인프라 코드 (CloudFormation)
│   └── cfn
│       ├── 01-github-oidc.yml      # GitHub OIDC 배포 권한
│       ├── 20-core-services.yml    # 핵심 AWS 리소스 (IVS, S3 등)
│       └── 30-eventbridge-webhook.yml   # IVS 이벤트 웹훅
│   
├── migrations                      # DB 마이그레이션 (aerich)
│   └── models/
│      
├── pyproject.toml                  # 의존성 및 설정
├── scripts
│   ├── ci                          # CI 스크립트
│   │   ├── check.sh                # lint/type 검사
│   │   └── test.sh                 # 테스트 실행
│   └── dev                         # 개발용 시드/유틸
│       ├── create_admin_user.py    .
│       ├── issue_token.py          .
│       ├── seed_artist.py          .
│       ├── seed_artist_kaggle.py   .
│       ├── seed_stream_sessions.py .
│       └── seed_users.py           .
├── tests/                          # 테스트 코드
└── uv.lock                         # 패키지 lock 파일


```
  


  <br>
  <br>


<hr>

## 📘 프로젝트 규칙 (Project Rules)

### 🌿 Git Workflow & Convention

#### 1.⏳ Git Flow

기본적으로 다음과 같은 브랜치들을 사용합니다.
```
- main: 제품의 배포 가능한 최종 상태를 저장하는 브랜치
- develop: 개발 중인 기능을 통합하는 브랜치
```    
- 기본 브랜치: `main`, `develop`
- `main`, `develop` 직접 push **금지**
- 모든 PR은 최소 **1인 이상 승인 필수**

<br>

#### 2. ✏️ Git Commit Convention

 - **🧱 기본 구조** : `[NEAR-티켓넘버]:Type: <작업 요약> `
 - **✅ 예시** :
   - `[NEAR-10] Feat: 유저 모델 추가`
   - `[NEAR-32] Fix: 마이그레이션 오류 수정`
   - `[NEAR-78] Refactor: 아티스트 조회 로직 리팩터링`
   - `[NEAR-140] Docs: README 구조 업데이트`
     
<details>
<summary><strong> 📐 Commit Template </strong></summary><br>

```
# 아래 1번 문항부터 주석 문구가 빈줄에 주석을 지우고 문항에 대한 내용을 작성하고 커밋을 완료해주세요.
#
# 1. 아래 형식에 맞춰 커밋 메시지 타이틀을 작성하세요:
# <타입>: <간결한 커밋 메시지 요약>
#
# 예시:
# Feat: 사용자 로그인 기능 추가
# Fix: 댓글 생성 시 발생하는 NullPointerException 수정
# Chore: 불필요한 로그 제거 및 변수명 수정
# Style: black, isort 코드 포매터 실행
# Docs: README에 프로젝트 설명 추가
# Build: Dockerfile 수정하여 실행 오류 해결
# Test: 게시글 API 단위 테스트 추가
# Refactor: 중복 코드 제거 및 함수 분리
# Hotfix: 프로덕션 장애 수정 - 잘못된 URL 패턴 수정

# 2. 변경 또는 추가사항을 아래에 간략하게 작성하세요 ( 필수 )
#
# 본문 내용은 어떻게 변경했는지 보다 무엇을 변경했는지 또는 왜 변경했는지를 설명합니다.

# 3. 이슈가 있다면 아래에 연결하세요 ( 선택 )
#
# 예시
# 관련 이슈: #123
```
</details>

 -   **🔖 Commit Type 정의**
   
<div align=center> 
  
|    타입    | 설명                           |
|:--------:| :--------------------------- |
|   Feat   | 새로운 기능 추가                    |
|   Fix    | 버그 수정                        |
|  Chore   | 기능 추가 없이 코드 수정 (오타, 주석 등)    |
|  Style   | 코드 포매팅 수정                    |
|   Docs   | 문서 수정 (README 등)             |
|  Build   | 빌드 관련 파일 수정                  |
|   Test   | 테스트 코드 추가/변경 (프로덕션 코드 변경 없음) |
| Refactor | 리팩터링 (기능 변화 없음)              |
|  Hotfix  | 긴급 수정                        |

</div>
  
  
### 🧑🏻‍💻 Code Convention

**1. 🧠 네이밍 규칙**
- **파일명**:  snake_case
- **클래스명**:  PascalCase
- **함수명**:  snake_case
-  **상수**:  UPPER_SNAKE_CASE

<br>

**2. 📍 URL 매핑 규칙**
- `Trailing Slash`는 추가하지 않는다

<br>

**3. ✨ Code Formatting**
- mypy
- ruff
- 위 두 가지를 사용하여 코드 포매팅과 타입 어노테이션을 준수한다.
<br>

**4. 🧪 Test Code**
- `PyTest`를 활용하여 테스트코드를 작성한다.
- Coverage 80% 이상을 유지한다.
<br>

**5. 🏷️ Swagger 문서**
- 각 API 별 태깅, API 요약, 구체적인 설명, 파라미터 등을 지정한다.
  - Tag는 관리자를 위한 라우터일 경우 '관리'를 명시
  - Summary에 해당 API의 요약 설명을 기재
  - Description에 해당 API의 구체적인 동작 설명

<br>

---

<br>

<div align=center> 

<h3><b>Backend Team Member</b></h3>

 | <a href=https://github.com/choi8154><img src="https://avatars.githubusercontent.com/u/223584123?v=4" width=100px/><br/><sub><b>@choi8154</b></sub></a><br/> | <a href=https://github.com/ji-min0><img src="https://avatars.githubusercontent.com/u/225418468?s=400&u=6e8c3d38b2d94b6bb502928613dad3b248b1851f&v=4" width=100px/><br/><sub><b>@ji-min0</b></sub></a><br/> | <a href=https://github.com/JaMiLy-max><img src="https://avatars.githubusercontent.com/u/223883617?v=4" width=100px/><br/><sub><b>@JaMiLy-max</b></sub></a><br/> |
|:-----------------------------------------------------------------------------------------------------------------------------------------------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------:|
|                                                                           최건희(팀장)                                                                           |                                                                                                    강지민                                                                                                     |                                                                               이아진                                                                               |

</div>

<br>
---

### 📋 Documents

> [ 🧚 요구사항 정의서 ](https://docs.google.com/spreadsheets/d/1Y07EfEfA7vvZu01o8cDpFd_HZBZDjZpZFykCiF2wXfs/edit?gid=0#gid=0)
> 
> [ 🪄 API 명세서 ]()
>
> [ 🔦 테이블 명세서 ]()
>
> [ 🪢 ERD ]()
> 
> <a href="" target="_blanck"><img width="2677" height="1964" alt="Near05" src="" /></a>
