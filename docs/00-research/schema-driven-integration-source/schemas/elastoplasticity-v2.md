# elastoplasticity-v2.json

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:smx:schema:elastoplasticity:2.0.0",
  "title": "Elastoplasticity (Simulation) Data",
  "x-table-key": "elastoplasticity_data",
  "description": "인장(+선택적 DMA) 시험에서 프로세싱된 탄소성 중립 데이터. '시험별 중립 데이터'의 대표 예로, 처리 파라미터(레시피)와 결과 곡선을 함께 보존한다.",
  "type": "object",
  "properties": {
    "elastoplasticity": {
      "type": "object",
      "properties": {
        "Data Information": {
          "type": "object",
          "properties": {
            "Elastoplasticity Data Record Name": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "record_name"
            },
            "Elastoplasticity Data ID": {
              "type": "string",
              "minLength": 1,
              "x-key": "elastoplasticity_data_id",
              "x-business-key": true,
              "x-indexed": true,
              "x-searchable": true,
              "x-id-rule": "EP_{ModelingType}_{Family}_{Category}_{Grade}_{Detail}_{SpecThickness}_{Orientation}_{UniqueNumber}"
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
            },
            "Tensile Data ID": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "tensile_data_ref",
              "x-reference": {
                "schema_key": "tensile-test",
                "pointer": "/tensile-test/Data Information/Tensile Data ID"
              }
            },
            "DMA Data ID": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "dma_data_ref",
              "x-reference": {
                "schema_key": "dma-test",
                "pointer": "/dma-test/Data Information/DMA Data ID"
              }
            }
          },
          "required": [
            "Elastoplasticity Data ID"
          ]
        },
        "Input Parameter": {
          "type": "object",
          "description": "처리 레시피(Process Recipe). 재현성을 위해 결과와 함께 불변 보존.",
          "properties": {
            "Interpolation Method": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "interpolation_method",
              "x-discrete-open": [
                "Strain Monotonicity Constraint, Stress Monotonic Spline",
                "Linear",
                "PCHIP"
              ]
            },
            "Data Sampling Method": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "sampling_method",
              "x-discrete-open": [
                "Even Sampling",
                "Adaptive Sampling"
              ]
            },
            "Toe Region Process": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "toe_region_process",
              "x-discrete-open": [
                "None",
                "Linear Extrapolation",
                "Offset Shift"
              ]
            },
            "Total Number of Data Point for Interpolation": {
              "type": [
                "integer",
                "null"
              ],
              "x-key": "interpolation_points"
            },
            "Elastic Modulus Definition": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "modulus_definition",
              "x-discrete-open": [
                "Linear Regression",
                "Chord",
                "Secant",
                "Manual",
                "From DMA"
              ]
            },
            "Initial Stress for Elastic Modulus (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "modulus_initial_stress",
              "x-unit": "MPa"
            },
            "Final Stress for Elastic Modulus (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "modulus_final_stress",
              "x-unit": "MPa"
            },
            "Offset Strain": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "offset_strain",
              "x-unit": "1"
            },
            "Define Modulus from DMA": {
              "type": [
                "boolean",
                "null"
              ],
              "x-key": "modulus_from_dma"
            },
            "Hardening Model": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "hardening_model",
              "x-discrete-open": [
                "Voce",
                "Swift",
                "Hockett-Sherby",
                "Ghosh",
                "Ludwik",
                "Hollomon",
                "Tabulated"
              ]
            },
            "Hardening Parameters (C1-C6)": {
              "type": [
                "array",
                "null"
              ],
              "items": {
                "type": "number"
              },
              "maxItems": 6,
              "x-key": "hardening_parameters"
            },
            "Optimization Method": {
              "type": [
                "string",
                "null"
              ],
              "x-key": "optimization_method",
              "x-discrete-open": [
                "Differential Evolution",
                "Least Squares (TRF)",
                "Multistart Least Squares"
              ]
            }
          },
          "additionalProperties": true
        },
        "Mechanical Properties": {
          "type": "object",
          "properties": {
            "Density (kg/m3)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "density",
              "x-unit": "kg/m3",
              "x-quantity": "physics.density"
            },
            "Poisson Ratio": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "poisson_ratio"
            },
            "Computed Elastic Modulus (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "computed_elastic_modulus",
              "x-unit": "MPa",
              "x-indexed": true
            },
            "Computed Yield Stress (MPa)": {
              "type": [
                "number",
                "null"
              ],
              "x-key": "computed_yield_stress",
              "x-unit": "MPa",
              "x-indexed": true
            }
          },
          "additionalProperties": true
        },
        "Strain-Stress Data": {
          "type": "object",
          "properties": {
            "Original Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "original_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Engineering Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa",
                "y_quantity": "mechanics.stress.engineering"
              }
            },
            "Total Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "total_curve",
              "x-curve": {
                "x_pointer": "/Series 1/True Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa",
                "y_quantity": "mechanics.stress.true"
              }
            },
            "Plastic Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "plastic_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Plastic Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa",
                "y_quantity": "mechanics.stress.true"
              }
            },
            "Interpolated Plastic Strain/Stress": {
              "type": [
                "object",
                "null"
              ],
              "x-key": "interpolated_plastic_curve",
              "x-curve": {
                "x_pointer": "/Series 1/Interpolated Plastic Strain (strain)",
                "x_unit": "1",
                "y_pointer": "/Series 1/Value (MPa)",
                "y_unit": "MPa",
                "y_quantity": "mechanics.stress.true"
              }
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
