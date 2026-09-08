const quantities: Record<string, string> = {
  "modulus.storage.prony.selected": "선택한 저장탄성률", "modulus.loss.prony.selected": "선택한 손실탄성률",
  "temperature.test": "시험 온도", "temperature": "온도",
  "strain.engineering": "공학 변형률", "mechanics.strain.engineering": "공학 변형률",
  "stress.engineering": "공학 응력", "mechanics.stress.engineering": "공학 응력",
  "strain.true_plastic": "진소성 변형률", "mechanics.strain.true_plastic": "진소성 변형률",
  "stress.hardening.selected": "선택한 경화 응력", "stress.hardening.voce": "Voce 경화 응력",
  "time": "시간", "frequency": "주파수", "frequency.cyclic": "주파수",
};
export function quantityLabel(value: string): string {
  return quantities[value] ?? value.replace(/^mechanics\./, "").replace(/[._]/g, " ").replace(/^\w/, letter => letter.toUpperCase());
}
export function modelFamilyLabel(value: string): string {
  const key = value.toLowerCase();
  if (key.includes("ogden")) return "Ogden–Prony";
  if (key.includes("tabulated") || key.includes("plasticity")) return "표 형식 소성";
  if (key.includes("maxwell")) return "일반화 Maxwell";
  if (key.includes("viscoelastic") || key.includes("prony")) return "선형 점탄성";
  if (key.includes("hyperelastic")) return "초탄성";
  if (key.includes("elastic")) return "선형 탄성";
  return "소재 모델";
}

export function unitLabel(unit: string): string { return ({ Cel: "°C", "kg/m3": "kg/m³" } as Record<string, string>)[unit] ?? unit; }
export function solverLabel(solver: string): string { return ({ openradioss: "OpenRadioss", abaqus: "Abaqus" } as Record<string, string>)[solver] ?? solver; }
export function unitSystemLabel(unit: string): string { return ({ kg_m_s: "kg·m·s", g_mm_ms: "g·mm·ms", tonne_mm_s: "t·mm·s" } as Record<string,string>)[unit] ?? unit; }
export function materialClassLabel(value: string): string {
  return ({ metal: "금속", polymer: "고분자", elastomer: "탄성체", composite: "복합재", ceramic: "세라믹" } as Record<string, string>)[value] ?? value;
}
