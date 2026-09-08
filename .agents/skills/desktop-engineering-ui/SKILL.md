---
name: desktop-engineering-ui
description: Capture and review CAE Material Platform screens for engineering readability, interaction continuity and responsive composition against the current product target.
---

# 공학 작업공간 시각 검토

## Prepare and implement from authority

[UI 원칙](../../../docs/product/frontend-ui-principles.md)의 현재 목표와 대상 화면·상태를 확인한다. 이전 비교안은 평가 이력이며 모든 안을 다시 만들 의무가 아니다.
해당 소스와 실제 현재 화면을 보고 차이를 정한다. 새로운 사용자 피드백은 전체 업무 목표 안에서 반영한다.
기존 화면의 업무·데이터 의미와 새 목표 배치를 구분한다. 등록 자료가 필요하면 service-reference inventory에서 해당 항목만 찾는다.

## Verify the complete screen

캡처 범위·크기·기록은 [시각 매트릭스](../../../docs/product/visual-acceptance-matrix.md)를 따른다. 실제 앱의 전후 상태를 캡처하고 원본 해상도와 필요한 영역 crop을 연다.
정보 위계, 공학 업무, 넓고 좁은 화면 구성을 각각 판단한다. 긴 이름·많은 목록·빈 결과·오류·미지원·입력 변경을 대상 업무에 맞게 확인한다.
물성값·단위·조건, 축·범례·곡선, 선택·주요 행동, 목록 복귀를 함께 본다. 특정 control 한 개의 개선으로 전체 화면 검토를 대신하지 않는다.
DOM geometry와 실제 장비 가독성, 테스트 통과와 사용자의 화면 선택을 구분한다. 이미지 크기나 축소 contact sheet만으로 승인하지 않는다.

## Independent review and approval

독립 검수가 배정되면 현재 diff·실제 캡처·검사 결과·적용 기준을 전달한다. 검수자는 읽기 전용으로 구체 결함과 근거를 제시한다.
담당 Main이 결과를 판단하고 수정한다. 소스/증거가 바뀌면 영향 범위를 다시 검증한다. 이 skill은 모델 배정·필수 agent 수·게시 권한을 정하지 않는다.
