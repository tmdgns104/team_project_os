# Team Project OS 운영 가이드

이 문서는 현재의 단일 FastAPI + SQLite 배포를 소규모 팀에서 안정적으로
운영하기 위한 기준입니다. 사용자 로그인/RBAC, SSO/OIDC, 다중 테넌트 격리가
필요한 조직 배포는 별도 설계 승인이 필요합니다.

## 1. 배포 전 체크리스트

1. 32자 이상의 임의 `APP_ACCESS_KEY`를 생성합니다.
2. `PROJECT_OS_ALLOWED_HOSTS`에 실제 도메인 또는 접속 IP만 기록합니다.
3. `PROJECT_OS_SEED_DEMO=0`을 유지합니다.
4. HTTPS와 요청 본문 제한을 담당할 Reverse Proxy를 앞단에 둡니다.
5. `/data` Docker Volume의 스냅샷/백업 위치와 복구 담당자를 정합니다.
6. `/api/health/live`와 `/api/health/ready`를 각각 liveness/readiness probe로
   모니터링합니다.

접속키 생성 예시:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Production 모드에서는 빈 값, 32자 미만, 예시 문자열, Host 와일드카드를
감지하면 서버가 시작되지 않습니다.

## 2. 주요 환경 변수

| 변수 | 기본값 | 운영 기준 |
|---|---|---|
| `PROJECT_OS_ENV` | `development` | Docker는 `production` |
| `APP_ACCESS_KEY` | 빈 값 | Production은 32자 이상 필수 |
| `PROJECT_OS_ALLOWED_HOSTS` | `localhost,127.0.0.1` | 실제 접속 도메인/IP allowlist |
| `PROJECT_OS_DB` | `./project_os.db` | Docker는 `/data/project_os.db` |
| `PROJECT_OS_SEED_DEMO` | 개발 `1`, 운영 `0` | 운영 `0` 권장 |
| `PROJECT_OS_MAX_REQUEST_BYTES` | `2000000` | 앱 제한, Proxy에도 별도 설정 |
| `PROJECT_OS_SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite lock 대기 시간 |
| `PROJECT_OS_SESSION_DIR` | 사용자 홈 아래 세션 폴더 | CLI 세션 저장 위치 override |
| `PROJECT_OS_BRIDGE_CONFIG` | 사용자 홈 설정 파일 | Bridge 설정/토큰 파일 override |

## 3. 상태 확인

- `GET /api/health/live`: ASGI 프로세스가 응답 가능한지 확인합니다.
- `GET /api/health/ready`: SQLite 연결과 스키마 조회가 가능한지 확인합니다.
- `GET /api/health`: V0.14 호환 endpoint입니다.

Readiness가 `503`이면 새 요청을 보내지 말고 DB Volume 권한, 디스크 용량,
SQLite lock 및 컨테이너 로그를 확인합니다.

## 4. 데이터 보호

SQLite는 WAL 모드로 동작합니다. 파일 하나만 실행 중에 임의 복사하면 WAL의
최신 변경이 누락될 수 있으므로 다음 중 하나를 사용합니다.

- 서비스 정지 후 `/data` Volume 전체(`project_os.db`, `-wal`, `-shm`) 스냅샷
- SQLite Online Backup API를 사용하는 조직 표준 백업 도구

복구는 기존 DB를 덮어쓰는 파괴적 작업입니다. 서비스 정지, 백업 무결성 확인,
복구 대상 승인, 원본 보존 후 수행하고 `/api/health/ready`와 핵심 프로젝트
snapshot/export를 확인합니다.

## 5. 알려진 운영 경계

- 현재 `APP_ACCESS_KEY`는 팀 공유 키이며 사용자별 권한이나 감사 주체를
  제공하지 않습니다.
- SQLite는 단일 인스턴스와 소규모 쓰기 부하에 적합합니다. 여러 API 인스턴스,
  고빈도 동시 쓰기, DB failover가 필요하면 서버 DB로의 설계 변경이 필요합니다.
- TLS, rate limit, chunked request body 제한, 접근 로그 보존은 Reverse Proxy 또는
  플랫폼 계층에서도 설정해야 합니다.
- 기존 V0.14 Bridge의 query-token API는 호환되지만 새 Bridge는 URL 로그 유출을
  피하기 위해 `Authorization: Bearer`를 사용합니다.

