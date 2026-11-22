# Feasibility: local Qwopus Flash conversion on a Dell with 32 GiB RAM

## Decision: feasible in principle, full conversion not implemented

Garlic's original `pc/modal_qwen35_9b.py` declares a 64-GiB Modal
worker. It reads one source tensor at a time using safetensors and quantizes
layers sequentially, **but** its `get` function materializes the entire
float32 tensor. In addition, `np.concatenate` builds full gate/up,
QKV and other matrices, and temporary NumPy arrays for q3/q4 can multiply
peak RAM. The 248,320 x 4096 embedding and 248,320 x 4096 output head
are especially large. Thus running the unmodified script on 32 GiB
would be unsafe; the 64-GiB figure is a requirement of the provided Modal
recipe, not a proven hard architectural minimum.

Garlic's `pc/checkpoint.py` already supports HTTP range reads of individual
safetensors segments. `blackserv_coder/streaming.py` implements a bounded
2-D row reader using that existing checkpoint metadata, without PyTorch.
The quantization tests establish that row-wise q3 and q4 give the same arrays
as the original whole-matrix quantizers on the tested synthetic data.

## Test evidence (22 November 2026)

- Model `Jackrong/Qwopus3-5-9B-Coder-Flash`: 427 tensors, BF16, MTP
  structural validation PASS via Garlic checkpoint.py.
- A live HTTP range request successfully returned **2 rows** from
  `model.language_model.layers.0.mlp.down_proj.weight`, shape
  [4096, 12288], BF16, decoded into float32 shape [2, 12288];
  all values finite.
- Five streaming unit tests passed: BF16/F16/F32 decode, chunk bounds,
  q3/q4 equivalence and rejection of invalid row intervals.
- No entire weight shard, quantized model or large paid resources downloaded.
- Dell currently has 32 GiB RAM and >600 GiB free on D:.

## Remaining engineering tasks

1. Implement a streaming writer for q4i/q3i **identical byte layout** to
   Garlic; row-tile alignment: 64 for q3i/q4i, 128 for q3s/q4s.
2. Handle combined QKV and gate/up weights through bounded segments,
   with deterministic output ordering and per-tensor checksums.
3. Convert huge embedding and lm_head in bounded blocks, retaining Garlic's
   exact vocabulary selection and GPU/CPU memory layout.
4. Convert and validate the model-specific MTP head.
5. Resume/retry interrupted downloads; protect disk budget and write
   to temporary paths before atomic publication.
6. Compare output bytes and numerical dequantization against Garlic's
   original reference on representative sample tensors.
7. Run full source model conversion (BF16 weights ~18 GiB before temporary
   data, size to be measured), validate with `upload_model.py --dry-run`,
   then test Garlic 1.21 PS4 inference and benchmarks.

**Not yet proven:** whole-model conversion within 32 GiB peak RAM, byte-for-byte
compatible model artifacts, model inference, PS4 runtime speed or coding quality.
This phase only proves bounded row reads and quantizer equivalence on samples.
