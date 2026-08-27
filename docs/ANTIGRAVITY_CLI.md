# Antigravity CLI 연결

Team Project OS Local Bridge는 `antigravity` Provider를 지원합니다.

## 1. 설치 및 최초 로그인

공식 Antigravity CLI 문서에 따라 `agy`를 설치한 뒤, 먼저 터미널에서 한 번 실행해 인증과 workspace trust를 완료합니다.

```bash
agy
```

## 2. 감지 확인

```bash
python local_bridge/bridge.py doctor
```

`Antigravity CLI: OK`가 표시되어야 합니다.

## 3. Project OS에 등록

```bash
python local_bridge/bridge.py register \
  --server http://SERVER_IP:8000 \
  --project 1 \
  --member "내 이름" \
  --provider antigravity \
  --repo /path/to/repository
```

Windows CMD 예시:

```bat
python local_bridge\bridge.py register --server http://SERVER_IP:8000 --project 1 --member "내 이름" --provider antigravity --repo D:\my-project
```

## 4. Task 실행

```bash
python local_bridge/bridge.py run --repo /path/to/repository --once
```

Bridge는 기본적으로 다음 형태의 공식 headless 모드를 사용합니다.

```bash
agy -p "<Team Project OS task prompt>" --output-format text --print-timeout 45m
```

Team Project OS는 `--dangerously-skip-permissions`를 기본으로 붙이지 않습니다. Antigravity CLI의 사용자/프로젝트 permission 설정을 사용하세요.

공식 문서: https://www.antigravity.google/docs/cli/headless/
