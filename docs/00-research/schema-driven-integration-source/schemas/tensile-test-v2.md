# tensile-test-v2.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:smx:schema:tensile-test:2.0.0",
  "title": "Tensile Test Data",
  "x-table-key": "tensile_test",
  "type": "object",
  "properties": {
    "tensile-test": {
      "type": "object",
      "properties": {
        "Data Information": {
          "type": "object",
          "properties": {
            "Tensile Test Data Record Name": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "record_name"
            },
            "Tensile Data ID": {
              "type": "string",
              "minLength": 1,
              "x-key": "tensile_data_id",
              "x-business-key": true,
              "x-indexed": true,
              "x-searchable": true,
              "x-id-rule": "TensileTest_{Family}_{Category}_{Grade}_{SpecThickness}_{Orientation}_{UniqueNumber}"
            },
            "Sample Type ID": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "sample_type_id"
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
            "Tensile Data ID"
          ]
        },
        "Test Condition": {
          "type": "object",
          "properties": {
            "Specimen Number": {
              "type": [
                "integer",
                "null"
              ],
              "x-key": "specimen_number"
            },
            "Testing Group": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "testing_group",
              "x-searchable": true
            },
            "Instrument Name": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "instrument_name"
            },
            "Operator": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "operator"
            },
            "Sensor Type": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "sensor_type"
            },
            "Specimen Standard": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "specimen_standard",
              "x-discrete-open": [
                "ASTM E8 Sheet-type",
                "ASTM D638 Type1",
                "ISO 527-2 1A"
              ]
            },
            "Tensile Speed for Elastic Region (mm/min)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "speed_elastic",
              "x-unit": "mm/min"
            },
            "Tensile Speed for Plastic Region (mm/min)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "speed_plastic",
              "x-unit": "mm/min"
            },
            "Preload (N)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "preload",
              "x-unit": "N"
            },
            "Specimen Real Thickness a0 (mm)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "real_thickness",
              "x-unit": "mm"
            },
            "Specimen Real Width b0 (mm)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "real_width",
              "x-unit": "mm"
            },
            "Gauge Length (mm)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "gauge_length",
              "x-unit": "mm"
            },
            "Temperature (degC)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "temperature",
              "x-unit": "degC"
            },
            "Run Date": {
              "type": [
                "string",
                "null"
              ],
              "format": "date",
              "x-key": "run_date"
            }
          },
          "additionalProperties": true
        },
        "Test Result": {
          "type": "object",
          "properties": {
            "Tensile Test Raw Data_Extensometer-Load": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "raw_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Extensometer (mm)",
                "x_unit": "mm",
                "x_quantity": "mechanics.displacement",
                "y_pointer": "/Series 1/Value (N)",
                "y_unit": "N",
                "y_quantity": "mechanics.force"
              }
            },
            "Strain at break (%)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "strain_at_break",
              "x-unit": "%"
            },
            "Strain (plastic) at Fmax (%)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "plastic_strain_at_fmax",
              "x-unit": "%"
            },
            "Yield Strain (%)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "yield_strain",
              "x-unit": "%"
            },
            "Upper Yield Point (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "upper_yield_point",
              "x-unit": "MPa"
            },
            "Lower Yield Point (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "lower_yield_point",
              "x-unit": "MPa"
            },
            "Force maximum (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "force_maximum",
              "x-unit": "MPa",
              "x-indexed": true
            },
            "Force at proof stress 0.2% (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "proof_stress_02",
              "x-unit": "MPa",
              "x-indexed": true
            },
            "Work hardening coefficient k (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "work_hardening_k",
              "x-unit": "MPa"
            },
            "Work hardening exponent n": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "work_hardening_n"
            },
            "Vertical anisotropy r": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "anisotropy_r"
            }
          },
          "additionalProperties": true
        }
      },
      "required": [
        "Data Information",
        "Test Result"
      ]
    }
  },
  "additionalProperties": false
}
```
