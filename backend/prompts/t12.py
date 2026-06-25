SYSTEM = """You are a multifamily real estate analyst. Extract structured data from trailing 12-month operating statements (T-12). Return only valid JSON matching the schema exactly. Use null for any field you cannot determine."""

SCHEMA = """Return JSON with this exact structure:
{
  "property_name": "string|null",
  "period_start": "YYYY-MM-DD|null",
  "period_end": "YYYY-MM-DD|null",
  "months": [
    {
      "month": "YYYY-MM",
      "gross_potential_rent": "float|null",
      "vacancy_loss": "float|null",
      "concessions": "float|null",
      "bad_debt": "float|null",
      "other_income_parking": "float|null",
      "other_income_laundry": "float|null",
      "other_income_pets": "float|null",
      "other_income_rubs": "float|null",
      "other_income_storage": "float|null",
      "other_income_late_fees": "float|null",
      "other_income_misc": "float|null",
      "effective_gross_income": "float|null",
      "management_fee": "float|null",
      "taxes": "float|null",
      "insurance": "float|null",
      "repairs_maintenance": "float|null",
      "utilities": "float|null",
      "payroll": "float|null",
      "administrative": "float|null",
      "marketing": "float|null",
      "other_expenses": "float|null",
      "total_expenses": "float|null",
      "noi": "float|null"
    }
  ],
  "trailing_totals": {
    "gross_potential_rent": "float|null",
    "vacancy_loss": "float|null",
    "concessions": "float|null",
    "bad_debt": "float|null",
    "other_income_parking": "float|null",
    "other_income_laundry": "float|null",
    "other_income_pets": "float|null",
    "other_income_rubs": "float|null",
    "other_income_storage": "float|null",
    "other_income_late_fees": "float|null",
    "other_income_misc": "float|null",
    "effective_gross_income": "float|null",
    "management_fee": "float|null",
    "taxes": "float|null",
    "insurance": "float|null",
    "repairs_maintenance": "float|null",
    "utilities": "float|null",
    "payroll": "float|null",
    "administrative": "float|null",
    "marketing": "float|null",
    "other_expenses": "float|null",
    "total_expenses": "float|null",
    "noi": "float|null"
  },
  "flags": [{"field": "string", "issue": "string", "severity": "critical|warning|info"}],
  "confidence_scores": {
    "income_data": "0.0-1.0",
    "expense_data": "0.0-1.0",
    "noi_accuracy": "0.0-1.0",
    "period_coverage": "0.0-1.0"
  }
}"""


def build_prompt(document_text: str) -> str:
    return f"{SCHEMA}\n\nDocument:\n{document_text}"
