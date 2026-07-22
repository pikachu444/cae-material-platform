# Reference Sources

## 1. Official Product Sources

### Ansys Granta MI

- Finding materials data  
  https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Materials_Gateway/gw/finding_materials_in_your_granta_mi_database.html

- Browsing: Database, Profiles, Contents tree, Subsets  
  https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/GetStart_Profile.html

- Browse, Search and Chart  
  https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Selector/sel_edu/browse_search_chart.html

- Viewing search results and exporting Material Cards  
  https://ansyshelp.ansys.com/public/Views/Secured/Granta/v252/en/Granta_MI/one_mi/tab_list.html

- Application overview: search/list/scatter/curve/import/workflow  
  https://ansyshelp.ansys.com/public/Views/Secured/Granta/v252/en/Granta_MI/one_mi/welcome_to_granta_mi.html

- Tabular data progressive disclosure  
  https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/Datasheet_tabulardata.html

### Altair/Simcenter Material Data Center

- AMDC private database feature overview  
  https://2025.help.altair.com/altairone/topics/materialsdb/admin_dashboard_about_r.htm

- Material Data Center interface tutorial  
  https://help.altair.com/2022/altairone/prod_help/altair_amdc/topics/materialsdb/tutorial_amdc_interface_r.htm

- Material Data Center CAE Model download example  
  https://2022.help.altair.com/2022/ss/en_us/topics/simsolid/external_interface/external_interface_amdc_r.htm

### Altair/Simcenter Material Modeler

- Extrapolation  
  https://help.altair.com/material_modeler/topics/material_modeler/extrapolation_t.htm

- Generate Material Card  
  https://help.altair.com/material_modeler/topics/material_modeler/material_card_generate_t.htm

- Import raw material and create advanced card  
  https://help.altair.com/material_modeler/topics/material_modeler/tutorials/amm_failure_criteria_create_r.htm

- Validate solver-ready card  
  https://help.altair.com/material_modeler/topics/material_modeler/tutorials/amm_validate_run_solver_r.htm

## 2. UI Design References

- Carbon Design System: Data Table  
  https://v10.carbondesignsystem.com/components/data-table/usage/

- GOV.UK Design System: Details / progressive disclosure  
  https://design-system.service.gov.uk/components/details/

- WCAG 2.2  
  https://www.w3.org/TR/WCAG22/

- WCAG contrast minimum  
  https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html

- WCAG target size minimum  
  https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

## 3. Repository Evidence

- `README.md`
- `AGENTS.md`
- `IMPLEMENTATION_STATUS.md`
- `docs/00-research/ux-reference-analysis.md`
- `docs/00-research/ux-layout-review/README.md`
- `docs/00-research/ux-layout-review/similarity-report.md`
- `docs/00-research/ux-layout-review/region-annotations.json`
- `docs/01-product/product-vision.md`
- `docs/01-product/product-experience-spec.md`
- `docs/01-product/gui-functional-parity-plan.md`
- `docs/00-research/official-product-research.md`
- `docs/00-research/product-capability-map.md`
- `docs/13-delivery/backlog.md`
- `apps/web/src/app.tsx`
- `apps/web/src/material-database-explorer.tsx`
- `apps/web/src/material-modeling-workspace.tsx`
- `apps/web/src/common-processing-workbench.tsx`
- `apps/web/src/canonical-test-data-workbench.tsx`
- `apps/web/src/styles.css`
- `docs/17-evidence/reports/t85-engineering-modeling-shell.md`
- `docs/17-evidence/reports/t91-material-database-parity.md`
- `docs/17-evidence/reports/t92-search-admin-recipe-batch.md`
- `docs/17-evidence/reports/t93-clean-product-acceptance.md`

## 4. Source Interpretation Rules

- 공식 자료는 기능과 사용자 workflow의 존재를 확인하는 근거로만 사용한다.
- 경쟁 제품의 내부 schema, algorithm, storage와 private API를 추정하지 않는다.
- 화면 구조는 brand pixel copy가 아니라 region topology, dominant-area ratio, density, surface grammar,
  selection continuity, action position과 progressive disclosure 단위로 비교한다.
- search, filter, governed Tree, list, datasheet, curve review와 CAE card delivery interaction principle을
  반응형 시안과 정량 측정으로 검증한다.
- 최신 제품명과 과거 도움말 제품명이 다를 수 있으므로 문서에 표시된 이름을 유지한다.
