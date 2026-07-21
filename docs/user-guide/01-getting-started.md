# 서비스 실행과 연결

## 준비물

- 실행 중인 Docker Desktop
- 이 저장소 checkout
- 실제 회사 데이터가 아닌 제공된 synthetic example data

## 실행

저장소 root의 PowerShell 또는 bash에서 다음 중 하나를 실행합니다.

```powershell
make demo
```

GNU Make를 사용할 수 없으면 다음 명령을 사용합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml up --build
```

모든 서비스가 준비된 뒤 다음 주소를 엽니다.

- Web: <http://127.0.0.1:5173>
- 최근 작업과 검토 진입은 **Activity**에서 확인합니다.

## Demo workspace 시작

1. Web 주소를 엽니다.
2. **Preparing your workspace…**가 사라질 때까지 기다립니다.
3. 상단 오른쪽에 **Demo workspace**가 표시되는지 확인합니다.
4. 기본 `/materials` 검색에서 기존 Material을 찾습니다. 적절한 Material/card가 없을 때만
   **Modeling**의 Data로 이동합니다.

Demo session은 `demo` mode에서만 자동으로 준비됩니다. production에서는 같은 자리에 일반
로그인 화면이 표시되며 사용자는 내부 연결 정보나 인증 문자열을 다루지 않습니다.

![Search-first Materials 기본 화면](../15-demo/images/ux-redesign-v2/final-materials-1440x900.png)

## 첫 Material 만들기

1. 일반 탐색은 **Materials → Browse Tree**, 생성·schema 관리는 우측 workspace menu의
   **Administration**을 엽니다.
2. 이름, code, family와 class를 입력합니다.
3. Steel은 `metal`, 일반 점탄성 polymer는 `polymer`, Ogden--Prony는 `elastomer`를 선택합니다.
4. Material 상세에서 State를 만들고 density, Young's modulus, Poisson ratio를 SI 단위로
   입력합니다.
5. 일반 상세에서는 `rN` 문맥만 확인하고 full revision ID는 Evidence 또는 Administration에서
   확인합니다.

저장할 때마다 새 immutable revision이 생깁니다. 브라우저 form을 고치는 것이 이미 저장된
revision을 바꾸지 않습니다.

상단 메뉴와 Material 문맥 탭의 역할, 분류·mapping·다운로드 문제 해결은
[메뉴와 Material 작업공간 사용법](10-navigation-and-troubleshooting.md)을 참고하십시오.

![Material 상세](../15-demo/images/e2e-material-detail.png)

## 종료와 데이터 주의

일반 종료에는 `docker compose ... down`을 사용합니다. `down -v`는 demo volume을 삭제하므로
보존할 demo가 없을 때만 개발 문서의 검증 절차에 따라 사용하십시오. Production 또는 다른
프로젝트에 demo teardown 명령을 복사하지 마십시오.
