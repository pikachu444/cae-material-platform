# fld-test-v1.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:smx:schema:fld-test:1.0.0",
  "title": "FLD Test Data",
  "x-table-key": "fld_test",
  "description": "성형한계도(Forming Limit Diagram). 다른 시험과 필드가 거의 겹치지 않는 독립 데이터 타입의 예 — 스키마 템플릿이 이런 타입도 코드 수정 없이 수용하여 화면을 보이는 케이스.",
  "type": "object",
  "properties": {
    "fld-test": {
      "type": "object",
      "properties": {
        "Data Information": {
          "type": "object",
          "properties": {
            "FLD Data Record Name": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "record_name"
            },
            "FLD Data ID": {
              "type": "string",
              "minLength": 1,
              "x-key": "fld_data_id",
              "x-business-key": true,
              "x-indexed": true,
              "x-searchable": true
            },
            "Technical Data ID": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "technical_data_ref",
              "x-reference": {
                "schema_key": "technical-data",
                "pointer": "/technical-data/Data Information/Technical Data ID"
              }
            }
          },
          "required": [
            "FLD Data ID"
          ]
        },
        "Test Condition": {
          "type": "object",
          "properties": {
            "Test Standard": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "test_standard",
              "x-discrete-open": [
                "ISO 12004-2 (Nakajima)",
                "ISO 12004-2 (Marciniak)"
              ]
            },
            "Punch Diameter (mm)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "punch_diameter",
              "x-unit": "mm"
            },
            "Punch Speed (mm/min)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "punch_speed",
              "x-unit": "mm/min"
            },
            "Lubrication": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "lubrication"
            },
            "Specimen Widths (mm)": {
              "type": [
                "array",
                "null"
              ],
              "items": {
                "type": "number"
              },
              "x-key": "specimen_widths"
            }
          },
          "additionalProperties": true
        },
        "Test Result": {
          "type": "object",
          "properties": {
            "Forming Limit Curve": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "flc_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Minor Strain (strain)",
                "x_unit": "1",
                "x_quantity": "mechanics.strain.minor",
                "y_pointer": "/Series 1/Major Strain (strain)",
                "y_unit": "1",
                "y_quantity": "mechanics.strain.major"
              }
            },
            "FLC0": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "flc0",
              "x-unit": "1",
              "description": "Plane strain 한계 변형률"
            }
          },
          "additionalProperties": true
        }
      },
      "required": [
        "Data Information"
      ]
    }
  },
  "additionalProperties": false
}
```
