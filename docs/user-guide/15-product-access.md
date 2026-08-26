# 제품 역할 및 접근 상태

제품 역할은 `User`, `Reviewer`, `Administrator` 세 가지입니다. Access는 사람 또는 팀을 **Member**로
표시하고, 각 역할에 서버가 부여한 고정 작업 묶음을 **Permissions**로 보여 줍니다. 관리자는 개별
permission을 직접 추가하거나 제거하지 않습니다.

| 역할 | Permissions |
| --- | --- |
| User | Processing & calibration, Solver Card export |
| Reviewer | Processing & calibration, Model approval, Solver Card export |
| Administrator | Schema configuration, Catalog editing, Processing & calibration, Solver Card export |

Model approval은 Reviewer 역할에만 포함됩니다. Administrator는 Database 구조, 실제 Record, 형식 정의,
전달과 Access를 관리하지만 Reviewer의 승인 permission을 자동으로 얻지 않습니다.

## Access 목록 읽기

1. 관리자 계정으로 **Administration → Access**를 엽니다.
2. `Member | Role | Permissions | Action` 열에서 현재 접근과 과거 회수 이력을 확인합니다.
3. Member는 접근을 받는 사람의 ID 또는 팀 이름이고 Role은 `User`, `Reviewer`, `Administrator` 중
   하나입니다. Permissions는 선택 Role에서 서버가 계산한 값입니다.
4. 현재 접근에는 **Remove access**가 있고 회수된 이력은 `Removed`로 남습니다.

## 접근 부여

이 작업은 Administrator만 할 수 있습니다.

1. **Grant access**를 눌러 compact 입력 화면을 엽니다.
2. **Member type**에서 Team 또는 User ID를 고릅니다. Team은 Identity provider와 Team name을,
   사용자는 User ID를 입력합니다.
3. Role을 선택하고 **Permissions**를 확인합니다. Permissions는 읽기 전용 결과이며 개별 항목을
   편집하지 않습니다.
4. Maximum classification, organization 범위와 Reason을 결정한 뒤 **Grant access**를 실행합니다.
   저장 중에는 **Granting…**으로 바뀌어 중복 실행을 막습니다.

## 접근 회수

현재 행의 **Remove access**를 누르고 Reason을 입력한 뒤 다시 **Remove access**를 실행합니다. 기존
grant를 삭제하거나 덮어쓰지 않으며, 회수 시각과 사유가 immutable history에 남습니다. 역할을
바꾸려면 기존 접근을 회수한 뒤 새 Role로 다시 부여합니다.

권한이 없는 사용자는 assignment 목록·grant·remove API를 사용할 수 없습니다. export-controlled
접근은 별도 운영 승인을 거치며 일반 Role 선택만으로 부여되지 않습니다.

![1366px Access 목록](images/current/administration-access-1366x768.png)

![1440px Access 목록](images/current/administration-access-1440x900.png)

넓은 화면의 Access 표는
[1920×1080](images/current/administration-access-1920x1080.png),
[2560×1440](images/current/administration-access-2560x1440.png),
[3840×2160](images/current/administration-access-3840x2160.png)에서도 같은 열과 행 동작을 유지합니다.
