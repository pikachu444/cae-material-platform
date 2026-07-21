# Web workbench

React 19, TypeScript and Vite로 구성된 engineering workbench입니다. 일반 사용자 전역 메뉴는
`Materials | Modeling | Activity`이며 `/materials`가 기본 route입니다. Administration은
role-gated workspace menu에서 엽니다.

```powershell
npm run dev --workspace @cmp/web
npm run build --workspace @cmp/web
npm run test:web
```

제품 화면과 route를 변경할 때는 `docs/user-guide/`, navigation contract와 현재 screenshot
manifest를 같은 변경 단위에서 갱신하고 `uv run cmp-check-user-guide --root .`를 실행합니다.

