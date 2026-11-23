"""Small synthetic end-to-end test of Garlic mix layout and local converter."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from blackserv_coder.local_convert import convert_mix
from blackserv_coder.validate_mix import validate_mix
from q3 import quantize_q3, interleave_q3
from q4 import quantize_q4, interleave_q4


class FakeModel:
    prefix = "model.language_model."
    src = "synthetic-local-fixture"
    text_config = {"num_attention_heads":2,"head_dim":32,
                   "layer_types":["full_attention"],"linear_conv_kernel_dim":4}

    def __init__(self):
        self.arrays = {}
        self.raw = {}
        rng = np.random.default_rng(81)
        def mat(name, rows, cols):
            self.arrays[name] = rng.normal(0, 0.025, size=(rows, cols)).astype("<f4")
        def vec(name, length):
            self.arrays[name] = rng.normal(0, 0.025, size=(length,)).astype("<f4")
        p = self.prefix
        vec(p+"norm.weight",64)
        lp = p+"layers.0."
        vec(lp+"input_layernorm.weight",64)
        vec(lp+"post_attention_layernorm.weight",64)
        a=lp+"self_attn."
        vec(a+"q_norm.weight",32)
        vec(a+"k_norm.weight",32)
        mat(a+"q_proj.weight",128,64)
        mat(a+"k_proj.weight",64,64)
        mat(a+"v_proj.weight",64,64)
        mat(a+"o_proj.weight",64,64)
        mat(lp+"mlp.gate_proj.weight",64,64)
        mat(lp+"mlp.up_proj.weight",64,64)
        mat(lp+"mlp.down_proj.weight",64,64)
        mat("lm_head.weight",128,64)
        mat(p+"embed_tokens.weight",128,64)
        self.weight_map = {name:name for name in self.arrays}
        self.raw = {name:a.tobytes() for name,a in self.arrays.items()}

    def header(self, shard):
        a=self.arrays[shard]
        return (0,{shard:{"dtype":"F32", "shape":list(a.shape),
                          "data_offsets":[0,len(self.raw[shard])]}})

    def _get(self, shard, start, end):
        return self.raw[shard][start:end]

    def tensor(self, name):
        return self.arrays[name].copy()


class ConverterTests(unittest.TestCase):
    def test_synthetic_mix_matches_garlic_layout(self):
        model = FakeModel()
        with tempfile.TemporaryDirectory() as tmp:
            outfile=Path(tmp)/"sample-mix.bin"
            meta=convert_mix(model,outfile)
            blob=outfile.read_bytes()
            self.assertEqual(len(blob),meta["size"])
            self.assertEqual(validate_mix(outfile)["status"],"pass")
            self.assertEqual(meta["gpu_size"]%4096,0)
            self.assertTrue(outfile.with_suffix(".json").is_file())
            t=meta["tensors"]
            p=model.prefix+"layers.0."
            a=p+"self_attn."
            qmat=model.arrays[a+"q_proj.weight"].reshape(2,2,32,64)
            query=qmat[:,0].reshape(64,64)
            gate=qmat[:,1].reshape(64,64)
            combined=np.concatenate([query,model.arrays[a+"k_proj.weight"],
                model.arrays[a+"v_proj.weight"],gate])
            q,d=quantize_q4(combined)
            expected=b"".join(interleave_q4(q,d))
            rec=t["0.wqkv"]
            self.assertEqual(blob[rec["offset"]:rec["offset"]+rec["size"]], expected)
            gu=np.concatenate([model.arrays[p+"mlp.gate_proj.weight"],
                               model.arrays[p+"mlp.up_proj.weight"]])
            q,d=quantize_q3(gu)
            rec=t["0.wgu"]
            self.assertEqual(blob[rec["offset"]:rec["offset"]+rec["size"]],
                             b"".join(interleave_q3(q,d)))
            embed=model.arrays[model.prefix+"embed_tokens.weight"]
            q,d=quantize_q4(embed)
            expected=np.concatenate([q,d.view(np.uint8)],axis=1).tobytes()
            rec=t["embed"]
            self.assertEqual(blob[rec["offset"]:rec["offset"]+rec["size"]],expected)
            self.assertEqual(rec["rowbytes"],36)
            with self.assertRaises(FileExistsError):
                convert_mix(model,outfile)




class FakeLinearModel(FakeModel):
    text_config = {"num_attention_heads":2,"head_dim":32,
                   "layer_types":["linear_attention"],"linear_conv_kernel_dim":4}

    def __init__(self):
        super().__init__()
        p=self.prefix+"layers.0."
        for name in list(self.arrays):
            if name.startswith(p+"self_attn."):
                del self.arrays[name]
        rng=np.random.default_rng(116)
        a=p+"linear_attn."
        shapes = {"in_proj_qkv.weight":(1152,64),
                  "in_proj_z.weight":(1024,64),
                  "in_proj_b.weight":(32,64),
                  "in_proj_a.weight":(32,64),
                  "conv1d.weight":(1152,1,4),
                  "A_log":(32,), "dt_bias":(32,), "norm.weight":(32,),
                  "out_proj.weight":(64,1024)}
        for key,shape in shapes.items():
            self.arrays[a+key]=rng.normal(0,0.025,size=shape).astype("<f4")
        self.weight_map={name:name for name in self.arrays}
        self.raw={name:array.tobytes() for name,array in self.arrays.items()}


class LinearConverterTests(unittest.TestCase):
    def test_validator_rejects_corruption(self):
        import json
        from blackserv_coder.validate_mix import validate_mix
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"bad-mix.bin"
            convert_mix(FakeModel(),path)
            jpath=path.with_suffix(".json")
            original=json.loads(jpath.read_text())
            changed=json.loads(json.dumps(original))
            changed["tensors"]["0.wgu"]["size"] += 1
            jpath.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                validate_mix(path)
            jpath.write_text(json.dumps(original))
            with path.open("r+b") as file:
                file.truncate(path.stat().st_size-1)
            with self.assertRaises(ValueError):
                validate_mix(path)

    def test_resume_after_interrupted_tensor(self):
        class InterruptOnce(FakeModel):
            def __init__(self):
                super().__init__()
                self.interrupt = True
            def tensor(self, name):
                if self.interrupt and name.endswith("q_norm.weight"):
                    self.interrupt = False
                    raise ConnectionError("simulated disconnect")
                return super().tensor(name)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            baseline=root/"baseline.bin"
            resumed=root/"resumed.bin"
            convert_mix(FakeModel(), baseline)
            ck=InterruptOnce()
            with self.assertRaises(ConnectionError):
                convert_mix(ck, resumed)
            self.assertTrue((root/"resumed.bin.part").exists())
            self.assertTrue((root/"resumed.bin.progress.json").exists())
            convert_mix(ck,resumed)
            self.assertEqual(baseline.read_bytes(),resumed.read_bytes())
            self.assertFalse((root/"resumed.bin.progress.json").exists())
            self.assertFalse((root/"resumed.bin.part").exists())

    def test_linear_layer_mix_layout(self):
        model=FakeLinearModel()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lin-mix.bin"
            meta=convert_mix(model,path)
            blob=path.read_bytes()
            self.assertEqual(validate_mix(path)["status"],"pass")
            t=meta["tensors"]
            a=model.prefix+"layers.0.linear_attn."
            w=np.concatenate([model.arrays[a+k+".weight"] for k in
                ("in_proj_qkv","in_proj_z","in_proj_b","in_proj_a")])
            q,sc=quantize_q4(w)
            expected=b"".join(interleave_q4(q,sc))
            rec=t["0.w_in"]
            self.assertEqual(blob[rec["offset"]:rec["offset"]+rec["size"]],expected)
            self.assertTrue(all(name in t for name in (
                "0.wout","0.conv","0.A","0.dt_bias","0.gnorm","0.wgu","0.wdown")))
            rec=t["0.A"]
            got=np.frombuffer(blob[rec["offset"]:rec["offset"]+rec["size"]],
                              dtype="<f4")
            np.testing.assert_array_equal(got,
                -np.exp(model.arrays[a+"A_log"]))

if __name__ == "__main__":
    unittest.main()
