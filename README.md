# 레포 받고 해야하는 설정들
1. githooks 경로 설정하기
- .githooks를 git이 인식하도록 하는 명령어 : `git config core.hooksPath .githooks`
- .githooks 내의 파일에 권한 부여 : `chmod +x .githooks/*`
- .githooks가 등록이 됐는지 확인 : `git config --get core.hooksPath`