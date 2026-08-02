# 깨끗한 전체 제품 흐름 검증

`make demo`의 공개 합성 시드는 다음 exact-revision 흐름을 실제 PostgreSQL과 보호된 API로
생성합니다. 모든 수치는 제품 작동 확인용이며 승인된 설계 물성값이 아닙니다.

1. configurable Catalog Record를 DP780 Material revision에 연결합니다.
2. `cmp.test-data` JSON에 제작사, lot, 시험일, 작업자, 단위와 12점 인장 curve를 저장합니다.
3. 채널을 quantity semantics에 연결하는 Mapping Profile을 저장합니다.
4. engineering-to-true/plastic 변환과 공개 hardening 식 fitting/외삽 단계를 Recipe로
   draft한 뒤 published revision으로 고정합니다.
5. Recipe Batch를 실행합니다. 폴리머 두 경로와 금속 경로에는 preview에서 선택한 fit evidence가
   남고, 금속 경로에는 manual necking boundary override도 남습니다.
6. 선택된 Processing Output을 tabulated-plasticity IR과 Neutral Material JSON으로 승격합니다.
   DP780 hardening selected model revision에 중복 없이 pending review request 하나를 만듭니다.
   이 단계에서는 승인·release하지 않습니다.
7. 같은 Neutral revision에서 Abaqus `.inp`와 OpenRadioss `.rad`를 생성합니다. Materials의 **CAE
   Cards** 탭에서 각 행의 **Preview card**를 열고 전달 안내를 확인한 뒤 native card를 내려받습니다.
8. Test JSON, Mapping Profile, Recipe, Neutral JSON, 두 mapping report와 두 native card를
   checksum이 있는 ZIP으로 묶습니다.

## 실행과 자동 검증

```powershell
make demo
make demo-verify
make demo-e2e
```

`make demo-verify`는 batch source와 Processing Output의 fit/override evidence, DP780 exact model
revision의 pending review request, JSON·두 ASCII card와 ZIP을 다시 내려받아 저장된 SHA-256과
비교하고, ZIP 안의 `manifest.json`, `checksums.sha256`, `README.txt`를 검사합니다. `make demo-e2e`는
Materials에서 Abaqus card preview의 전달 안내를 확인한 뒤 card를 내려받고 Activity의 읽을 수 있는
review 대기 상태를 확인한 뒤 Exports 화면의 **Download ZIP**으로 같은 digest를 검사합니다.

## 화면에서 내려받기

1. [Activity](http://127.0.0.1:5173/activity)의 Advanced에서 **Bulk exports**를 누르거나
   호환 route [Exports](http://127.0.0.1:5173/exports)를 엽니다.
2. Material에서 `CMP-DEMO-DP780`을 선택합니다.
3. **CAE Cards** 탭에서 Abaqus 또는 OpenRadioss 행의 **Preview card**를 엽니다. 전달 안내를
   확인하고 확인란을 선택한 뒤 각각 **Download .inp** 또는 **Download .rad**를 눌러 native card를
   받습니다. 긴 카드는 미리보기 안에서 스크롤할 수 있습니다. 1920px 이상 화면에서는 같은 카드 값의
   응답 그래프도 함께 확인할 수 있습니다. 확인이 필요 없는 카드는 해당 행에서 바로 내려받습니다.
4. Activity로 이동해 selected model의 `Waiting for review` 항목이 보이는지 확인합니다. 승인·release는
   이 검증 단계에 포함하지 않습니다.
5. Test Data JSON, Mapping Profile, published Processing Recipe, Neutral Material JSON,
   Neutral mapping report와 native Solver Card의 exact revision을 확인합니다.
6. 이미 시드된 **Immutable bundles**의 **Download ZIP**을 누르거나 필요한 항목을 다시
   선택해 새 Bundle을 만듭니다.
7. 압축을 푼 뒤 `checksums.sha256`의 각 digest를 확인합니다.


실제 Abaqus/OpenRadioss 실행과 결과 비교는 이 검증 범위에 포함되지 않습니다.
