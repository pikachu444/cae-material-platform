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
- API health: <http://127.0.0.1:8000/api/v1/health>

## Demo identity 연결

1. 화면 오른쪽 위의 **Connection**을 엽니다.
2. **Use local demo identity**를 선택합니다.
3. **Save connection**을 누릅니다.
4. 상단에 connected 상태가 표시되는지 확인합니다.

Demo identity는 `demo` mode에서만 발급됩니다. production identity 또는 실제 회사 권한을
대체하지 않습니다.

## 첫 Material 만들기

1. 상단 **Materials**를 엽니다.
2. 이름, code, family와 class를 입력합니다.
3. Steel은 `metal`, 일반 점탄성 polymer는 `polymer`, Ogden--Prony는 `elastomer`를 선택합니다.
4. Material 상세에서 State를 만들고 density, Young's modulus, Poisson ratio를 SI 단위로
   입력합니다.
5. 화면의 Material/State/Property revision 번호를 확인합니다.

저장할 때마다 새 immutable revision이 생깁니다. 브라우저 form을 고치는 것이 이미 저장된
revision을 바꾸지 않습니다.

![Material 상세](../15-demo/images/e2e-material-detail.png)

## 종료와 데이터 주의

일반 종료에는 `docker compose ... down`을 사용합니다. `down -v`는 demo volume을 삭제하므로
보존할 demo가 없을 때만 개발 문서의 검증 절차에 따라 사용하십시오. Production 또는 다른
프로젝트에 demo teardown 명령을 복사하지 마십시오.
