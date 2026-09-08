---
name: material-platform-frontend-architecture
description: Review CAE frontend ownership or cross-feature state/API boundaries when those boundaries change; use the architecture checklist without a separate mandatory packet.
---

# 프론트엔드 경계 검토

[아키텍처의 짧은 점검표](../../../docs/architecture/frontend-architecture.md#경계가-바뀔-때의-짧은-점검표)를 작업 계획 안에서 확인한다.
상태·계산·API·UI 소유자, 보존할 공학 로직, 늦은 응답·미저장 편집·복구의 검증 방법을 결정한다.
이 skill은 선택적 진입점이며 React 변경마다 호출하거나 별도 명세서를 만들 필요가 없다. 제품·시각·게시 규칙을 여기 중복하지 않는다.
