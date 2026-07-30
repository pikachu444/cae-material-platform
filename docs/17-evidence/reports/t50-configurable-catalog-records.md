# T-50 configurable Catalog Record 검증 증거

검증일: `2026-07-18`

Docker Compose의 PostgreSQL 16, API 및 Vite web을 사용해 실제 저장·조회 흐름을 검증했다.

1. migration head `20260826_060_t50`까지 적용했다.
2. `Engineering Materials` Table에 `Material family` discrete Attribute와 `Manufacturer` text
   Attribute를 DB migration 없이 추가했다.
3. `Metals → Sheet metals` 중첩 Folder와 DP600, AA6061-T6 typed Record를 생성했다.
4. Young's modulus의 원본 값/단위와 정규화 값/단위를 함께 저장했다.
5. discrete facet이 Steel 1건과 Aluminum 1건을 반환하는지 실제 UI에서 확인했다.
6. DP600의 modulus를 210 GPa에서 205 GPa로 수정해 새 immutable revision을 생성했다.
7. UI에서 current exact value와 revision 1 → 2 차이를 확인했다.
8. 브라우저 console error가 0건임을 확인했다.

별도 PostgreSQL 통합 테스트는 fresh database와 non-bypass application role에서 Folder cycle,
typed value 제약, full-text/Attribute text 검색, discrete facet, normalized number range, revision 비교를
검증한다. 같은 테스트 파일에서 10,000개 Record의 bounded 100개 page와 정확한 검색 결과도 검증한다.

![Catalog Record 검색 및 datasheet](../images/historical-task-screenshots/t50-configurable-catalog-records.jpg)

![Record revision 비교](../images/historical-task-screenshots/t50-configurable-catalog-revision-compare.jpg)
