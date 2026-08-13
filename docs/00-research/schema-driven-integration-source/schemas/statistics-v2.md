# statistics-v2.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:smx:schema:statistics:2.0.0",
  "title": "Statistics Data",
  "x-table-key": "statistics_data",
  "description": "다수 시편 통계 대표 데이터. 분포 피팅과 평균/상·하위 5% envelope 곡선을 승인 대상 대표값으로 보존.",
  "type": "object",
  "properties": {
    "statistics": {
      "type": "object",
      "properties": {
        "Data Information": {
          "type": "object",
          "properties": {
            "Statistics Data Record Name": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "record_name"
            },
            "Statistics Data ID": {
              "type": "string",
              "minLength": 1,
              "x-key": "statistics_data_id",
              "x-business-key": true,
              "x-indexed": true,
              "x-searchable": true
            },
            "Source Tensile Data IDs": {
              "type": [
                "array",
                "null"
              ],
              "items": {
                "type": "string"
              },
              "x-key": "source_tensile_refs",
              "x-reference": {
                "schema_key": "tensile-test",
                "pointer": "/tensile-test/Data Information/Tensile Data ID",
                "cardinality": "many"
              }
            },
            "Excluded Tensile Data IDs": {
              "type": [
                "array",
                "null"
              ],
              "items": {
                "type": "string"
              },
              "x-key": "excluded_tensile_refs",
              "description": "이상치 판정으로 제외한 시편. 제외 사유는 Assessment 필드에."
            }
          },
          "required": [
            "Statistics Data ID"
          ]
        },
        "Statistical Model": {
          "type": "object",
          "properties": {
            "Distribution Model": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "distribution_model",
              "x-discrete": [
                "Normal",
                "Weibull",
                "Lognormal"
              ]
            },
            "Target Quantity": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "target_quantity",
              "x-discrete-open": [
                "Proof Stress 0.2%",
                "Tensile Strength",
                "Elastic Modulus",
                "Strain at Break"
              ]
            },
            "Mean": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "mean"
            },
            "Standard Deviation": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "std_deviation"
            },
            "Distribution Parameters": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "distribution_parameters",
              "additionalProperties": true
            },
            "Sample Count": {
              "type": [
                "integer",
                "null"
              ],
              "x-key": "sample_count"
            },
            "Outlier Assessment": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "outlier_assessment"
            }
          },
          "additionalProperties": true
        },
        "Envelope Curves": {
          "type": "object",
          "properties": {
            "Avg Plastic Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "avg_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Plastic Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa",
                "deviation_pointer": "/Series 1/Standard Deviation Stress (MPa)",
                "deviation_unit": "MPa"
              }
            },
            "Upper 5% Plastic Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "upper5_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Plastic Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa"
              }
            },
            "Lower 5% Plastic Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "lower5_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Plastic Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa"
              }
            }
          },
          "additionalProperties": true
        }
      },
      "required": [
        "Data Information",
        "Statistical Model"
      ]
    }
  },
  "additionalProperties": false
}
```
