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

## 1. 원본 업로드와 preview

1. Modeling의 **Data → Import JSON / CSV / XLSX → Open governed mapping workbench**를 열거나
   호환 주소 `/datasets/import`로 이동합니다. 화면 상단에서 복원된 Material/Material State와
   exact revision을 먼저 확인합니다.
2. 원본이 속하는 **Exact Test Run**을 선택합니다. 이후 Run의 최신 revision을 암묵적으로
   따라가지 않고 선택 당시 revision이 고정됩니다.
3. `CSV`, `TSV`, `XLSX` 중 실제 형식을 고릅니다.
4. CSV/TSV는 delimiter, header row, decimal separator를 명시합니다. XLSX는 sheet 이름을
   반드시 입력합니다.
5. **Upload immutable bytes and preview**를 실행합니다.

Preview는 header와 일부 row를 보여 주지만 mapping을 자동 승인하지 않습니다. 상태가
`needs_input`인 것은 오류가 아니라 사용자의 quantity/unit 확인이 필요하다는 뜻입니다.
원본 bytes와 SHA-256은 이 단계부터 변경하지 않습니다.

## 2. 재사용 가능한 Import Profile 승인

1. 시험 schema를 선택합니다.
   - monotonic tension/compression
   - planar tension, biaxial tension, simple shear
   - shear relaxation
2. independent/dependent column을 preview header에서 선택합니다.
3. 각 column의 원래 unit을 선택합니다. 예제 파일은 strain `%`, stress `MPa`입니다.
4. 조직에서 다시 알아볼 수 있는 Profile label을 입력합니다.
5. **Approve immutable Profile revision**을 실행합니다.

Profile은 file format, sheet/header/locale, column, quantity, original unit과 normalized unit을
고정한 revision입니다. 설정을 고칠 때 기존 Profile revision을 덮어쓰지 않고 새 revision을
만듭니다.

Force/displacement 원본을 사용할 때는 **Source is displacement / force**를 선택하고 양수인
initial gauge length와 cross-section area를 SI 단위로 입력해야 합니다. 이 geometry가 없으면
stress/strain 파생을 실행하지 않습니다. 이 경로는 monotonic tension/compression에만
허용됩니다.

## 3. exact Import Run 실행

1. 방금 승인한 **Approved Profile**을 선택합니다.
2. **Create raw + normalized SI Datasets**를 실행합니다.
3. 결과가 `succeeded`인지 확인하고 row count, raw Dataset revision ID, normalized Dataset
   revision ID를 확인합니다.

성공 결과는 다음을 분리해 보존합니다.

- Raw Asset/Artifact: 업로드한 원본 bytes와 checksum
- raw Dataset revision: 원래 channel 이름, quantity와 unit 의미
- normalized Dataset revision: SI로 변환된 별도 Parquet Artifact
- Import Run: exact Test Run, Raw Asset/Artifact와 Profile revision pin

형식, 숫자, 단위 또는 schema 검증이 실패하면 원본이나 성공 결과를 일부 수정하지 않습니다.
Run은 `failed` terminal evidence로 남고 failure code/detail과 발견한 row 번호를 표시합니다.
설정을 수정한 새 Profile revision으로 다시 실행하십시오.

## 안전 제한

- XLSX formula, macro, external link는 실행하지 않고 거부합니다.
- 표준 OOXML의 상대(`worksheets/sheet1.xml`)와 절대(`/xl/worksheets/sheet1.xml`) worksheet
  relationship는 둘 다 허용하지만, backslash와 `..` parent traversal은 거부합니다.
- 압축 해제 크기, member 수, row/column 수에는 상한이 있습니다.
- CSV/TSV encoding과 decimal separator를 추측해 조용히 바꾸지 않습니다.
- 다른 organization/project의 Profile, Run, Dataset은 PostgreSQL RLS로 보이지 않습니다.
- 현재 지원 목록 밖의 proprietary laboratory format은 별도 승인된 importer가 필요합니다.

다음 단계는 normalized Dataset을 Processing/Statistics 또는 Material Model calibration의 exact
Selection으로 고정하는 것입니다. 원본 Dataset에서 outlier row를 삭제하거나 평균 curve로
대체하지 마십시오.
