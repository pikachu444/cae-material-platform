import { expect, test } from "@playwright/test";

import {
  deriveNistSrm2491CyclicHzUpload,
  NIST_SRM_2491_DMA_FIXTURE_SHA256,
  NIST_SRM_2491_DMA_UPLOAD_SHA256,
  NIST_SRM_2491_HOLDOUT_SWEEP_ORDINAL,
  NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL,
  NIST_SRM_2491_REFERENCE_TEMPERATURE_K,
} from "./issue-392-dma-tts-fixture";

test("Issue #392 NIST SRM 2491 fixture preserves the governed upload contract", () => {
  const upload = deriveNistSrm2491CyclicHzUpload();
  const lines = upload.trimEnd().split("\n");

  expect(NIST_SRM_2491_DMA_FIXTURE_SHA256).toBe("e67ae6a2d4772b33b5a0ca9667449cc415a310b3399c7532304b7014083758d0");
  expect(lines).toHaveLength(97);
  expect(new TextEncoder().encode(upload).byteLength).toBe(4264);
  expect(lines[0]).toBe("source_sweep_ordinal,temperature_degC,frequency_Hz,storage_modulus_Pa,loss_modulus_Pa");
  expect(lines[1]).toBe("1,0.0,0.015915494309189534,2.950,148.182");
  expect(NIST_SRM_2491_DMA_UPLOAD_SHA256).toBe("f9730a7047cffe9ed808faf861ade1464efad069fd28cc117d1bfe80a0e44068");
  expect(NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL).toBe(4);
  expect(NIST_SRM_2491_REFERENCE_TEMPERATURE_K).toBe(303.15);
  expect(NIST_SRM_2491_HOLDOUT_SWEEP_ORDINAL).toBe(1);
});
