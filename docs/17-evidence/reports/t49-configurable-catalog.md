# T-49 configurable Catalog evidence

검증일: `2026-07-17`

Docker Compose의 PostgreSQL 16, API와 Vite web을 사용해 다음 흐름을 실행했다.

1. migration 059를 이전 revision으로 downgrade한 뒤 다시 `head`까지 upgrade했다.
2. signed local demo identity로 `Engineering Materials`와 `Test Records` Table을 생성했다.
3. `Young's modulus` number Attribute에 `modulus.elastic.young`/`Pa`를 저장했다.
4. `Source test` record-reference Attribute가 `Test Records` Table을 가리키게 했다.
5. 두 exact Attribute revision을 포함하는 Layout r1을 만들고 ETag로 r2를 추가했다.
6. saved Subset을 만들고 실제 UI에서 2 Tables, 2 Attributes, 1 Layout, 1 Subset을 확인했다.

자동화된 PostgreSQL 회귀는 fresh database와 non-bypass application role에서 schema round-trip,
Layout revision history, typed number metadata guard와 immutable child rows를 검증한다. 실제 record
form/search/facet/compare는 T-50이며 T-49 완료로 주장하지 않는다.

![Catalog schema designer](../images/historical-task-screenshots/t49-configurable-catalog.jpg)
