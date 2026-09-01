const WARNING_LABELS: Record<string, string> = {
  INPUT_PROCESS_METADATA_NOT_PROVIDED: "Input preparation not recorded",
  RANK_DEFICIENT: "Parameters not independently resolved",
  EXECUTION_REQUEST_INVALID: "Calculation request invalid",
};

export function polymerWarningLabel(code: string): string {
  return WARNING_LABELS[code] ?? "Review required";
}
