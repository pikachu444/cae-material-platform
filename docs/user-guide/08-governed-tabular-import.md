# CSV/TSV/XLSX 시험 데이터 승인과 Dataset 생성

이 절차는 T-41 governed importer를 사용해 공개 tabular 시험 파일의 원본을 변경 불가능한
Raw Asset으로 보존하고, 사람이 channel과 unit 의미를 승인한 뒤 raw Dataset과 normalized SI
Dataset을 별도로 만드는 방법을 설명합니다. 특정 시험기 vendor format을 자동 해석하거나
제조사별 숨은 기본값을 적용하지 않습니다.

## 준비

- Docker demo와 local demo identity를 연결합니다.
- Material 상세에서 Material State, Specimen, Test Method와 Test Run을 먼저 만듭니다.
- 예제는 [`reference-tensile.csv`](../../examples/data/reference-tensile.csv)를 사용합니다.
  값은 공개 시연용 synthetic data이며 설계나 재료 승인에 사용할 수 없습니다.

## Modeling Data에서 시작

일반 작업은 `/modeling?stage=data` 안에서 진행합니다. Data 상단의 출처 선택은 다음 세 가지입니다.

- **Library**: 현재 Material/Material State에 연결된 exact Test Data revision을 선택합니다. 각
  곡선의 **Include in processing and fit**와 **Show on plot**은 서로 다른 선택이며, 하나를
  바꿔도 다른 선택은 바뀌지 않습니다.
- **Local file**: CSV/TSV/XLSX 원본을 업로드하고 현재 Test Run에 연결합니다.
- **Test Data JSON**: canonical JSON을 검증하고 같은 그래프에서 먼저 확인합니다.

별도 `/datasets/import`와 `/datasets/test-json` 주소는 관리·진단용 고급 경로로 유지됩니다.

Data 작업면은 위쪽의 얕은 ribbon과 아래쪽의 persistent graph로 이어집니다. 두 영역 사이 수평
splitter를 드래그하거나 키보드로 조절할 수 있고, 사용자가 정한 크기는 화면을 다시 열어도
유지됩니다. 기본 ribbon은 178 px이며 그래프의 축과 grid는 계속 보입니다.

## 1. 원본 업로드와 preview

1. Modeling의 **Data → Local file**을 엽니다. 화면 상단에서 복원된 Material/Material State와
   exact revision을 먼저 확인합니다.
2. 원본이 속하는 **Exact Test Run**을 선택합니다. 이후 Run의 최신 revision을 암묵적으로
   따라가지 않고 선택 당시 revision이 고정됩니다.
3. native **Choose File**에서 CSV, TSV 또는 XLSX 원본을 고르고 **Inspect source**를 실행합니다.
   확장자와 실제 파일 설정은 이후 Profile에 함께 고정됩니다.
4. XLSX가 한 worksheet이면 자동 선택됩니다. 여러 worksheet이면 목록에서 실제 시험 데이터
   worksheet를 고른 뒤에만 header와 sample row를 읽습니다.
5. data name, maker, operator, laboratory와 현재 exact Test Run 문맥을 확인합니다.

Preview는 header와 일부 row를 보여 주지만 mapping을 자동 승인하지 않습니다. 상태가
`needs_input`인 것은 오류가 아니라 사용자의 quantity/unit 확인이 필요하다는 뜻입니다.
원본 bytes와 SHA-256은 이 단계부터 변경하지 않습니다.

## 2. 재사용 가능한 Import Profile 승인

기존 human-approved Profile이 format, worksheet, header/locale과 column 이름까지 정확히
일치하면 승인된 mapping 요약만 표시되고 각 필드를 다시 확인할 필요가 없습니다. 일치하는
Profile이 없거나 둘 이상이면 주의 표시가 난 항목만 확인합니다.

1. 미확정인 경우에만 시험 schema를 선택합니다.
   - monotonic tension/compression
   - planar tension, biaxial tension, simple shear
   - shear relaxation
2. 작은 select에서 Independent/Dependent 축의 source column을 preview header에서 선택합니다.
3. 각 축의 source unit을 선택합니다. 예제 파일은 strain `%`, stress `MPa`입니다. normalized
   unit은 변환 결과로 표시되며 원래 unit을 덮어쓰지 않습니다.
4. **Update preview**를 실행해 등록 전 curve와 original/normalized unit을 확인합니다.
5. 그래프가 의도한 시험을 나타낼 때 **Save Test Data**를 실행합니다.

Profile은 file format, sheet/header/locale, column, quantity, original unit과 normalized unit을
고정한 revision입니다. 설정을 고칠 때 기존 Profile revision을 덮어쓰지 않고 새 revision을
만듭니다.

Force/displacement 원본을 사용할 때는 **Source is displacement / force**를 선택하고 양수인
initial gauge length와 cross-section area를 SI 단위로 입력해야 합니다. 이 geometry가 없으면
stress/strain 파생을 실행하지 않습니다. 이 경로는 monotonic tension/compression에만
허용됩니다.

## 3. exact Import Run과 Test Data 등록

**Save Test Data**는 승인한 exact Profile로 Import Run을 먼저 실행합니다. 성공하면
같은 원본 bytes로 미리 본 canonical Test Data를 immutable revision으로 등록하고 Library에
선택합니다. Import Run이 실패하면 canonical Test Data 등록은 진행하지 않습니다.

성공 결과는 다음을 분리해 보존합니다.

- Raw Asset/Artifact: 업로드한 원본 bytes와 checksum
- raw Dataset revision: 원래 channel 이름, quantity와 unit 의미
- normalized Dataset revision: SI로 변환된 별도 Parquet Artifact
- Import Run: exact Test Run, Raw Asset/Artifact와 Profile revision pin

형식, 숫자, 단위 또는 schema 검증이 실패하면 원본이나 성공 결과를 일부 수정하지 않습니다.
mapping이 잘못된 동안에는 마지막 정상 graph를 그대로 두고 **Update preview**와 **Save Test Data**를
비활성화합니다. mapping을 고친 뒤에만 다시 preview하고 저장할 수 있습니다. Import Run은 `failed`
terminal evidence로 남고 failure code/detail과 발견한 row 번호를 표시합니다. 설정을 수정한 새
Profile revision으로 다시 실행하십시오.

## 안전 제한

- XLSX formula, macro, external link는 실행하지 않고 거부합니다.
- 표준 OOXML의 상대(`worksheets/sheet1.xml`)와 절대(`/xl/worksheets/sheet1.xml`) worksheet
  relationship는 둘 다 허용하지만, backslash와 `..` parent traversal은 거부합니다.
- 압축 해제 크기, member 수, row/column 수에는 상한이 있습니다.
- CSV/TSV encoding과 decimal separator를 추측해 조용히 바꾸지 않습니다.
- 다른 organization/project의 Profile, Run, Dataset은 PostgreSQL RLS로 보이지 않습니다.
- 현재 지원 목록 밖의 proprietary laboratory format은 별도 승인된 importer가 필요합니다.

다음 단계는 normalized Dataset을 Processing/Statistics 또는 Material Model calibration의 exact
Selection으로 고정하는 것입니다. **Process**에서는 원본과 선택한 처리 단계를 같은 그래프에서
구분해 보고 **Preview processing**으로 먼저 계산합니다. 검토가 끝난 경우에만 상단의
**Commit reviewed output**으로 immutable Processing Output을 만듭니다. 원본 Dataset에서 outlier
row를 삭제하거나 평균 curve로 대체하지 마십시오.
