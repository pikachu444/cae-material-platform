# Elastomer Ogden--Prony 카드

현재 Elastomer workflow는 one-term Ogden과 1~5 shear-Prony term을 수동 입력하는
`reference/non-production` 수직 기능입니다. 자동 multi-test Ogden fitting은 T-43 범위입니다.

## 절차

1. Material class를 `elastomer`로 만들고 State/Property Set을 준비합니다.
2. **Ogden--Prony** 영역에서 positive finite `mu`, `alpha`와 ordered Prony terms를 입력합니다.
3. shear ratio 합이 1 미만이고 relaxation time이 양수·strictly increasing인지 확인합니다.
4. exact Material/State/Property revision으로 immutable IR을 만듭니다.
5. target을 선택합니다.
   - Abaqus 2025: `*HYPERELASTIC, OGDEN, N=1`과 `*VISCOELASTIC`
   - OpenRadioss 2025: `/MAT/LAW62`
6. mapping report를 확인하고 report digest를 승인한 뒤 card를 생성합니다.
7. preview와 `.inp` 또는 `.rad` download를 확인합니다.

![OpenRadioss LAW62 preview](../15-demo/images/ogden-openradioss-law62.png)

## Mapping 해석

- Ogden μ/α와 shear-Prony는 두 target에서 explicit mapping입니다.
- Abaqus의 incompressible `D1=0`은 현재 reference convention에서 exact입니다.
- OpenRadioss LAW62는 volumetric response를 `nu=0.495`로 표현하므로 `approximated`입니다.
- 이 근사는 반드시 화면과 mapping report에 남으며 production 승인을 의미하지 않습니다.

선형 점탄성 IR을 LAW62로 우회시키거나 없는 bulk relaxation 값을 추측해서 입력하지 마십시오.
