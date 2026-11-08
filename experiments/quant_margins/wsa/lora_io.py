"""Write a PEFT-format LoRA adapter that vLLM (--enable-lora) loads over the W4A16 -ct base.
modules: {vllm_module_path: (A [r x in], B [out x r])}; delta W = B @ A (scaling lora_alpha / r = 1)."""
import json, os, torch
from safetensors.torch import save_file


def write_peft_adapter(out_dir, modules, base_model='google/gemma-4-31b-it-qat-w4a16-ct', extra=None, prefix='base_model.model.'):
    os.makedirs(out_dir, exist_ok=True)
    r = max(A.shape[0] for A, B in modules.values())
    tensors = {}
    for name, (A, B) in modules.items():
        assert A.shape[0] == B.shape[1]
        tensors[f'{prefix}{name}.lora_A.weight'] = A.to(torch.bfloat16).contiguous()
        tensors[f'{prefix}{name}.lora_B.weight'] = B.to(torch.bfloat16).contiguous()
    save_file(tensors, os.path.join(out_dir, 'adapter_model.safetensors'))
    targets = sorted({n.split('.')[-1] for n in modules})
    cfg = {'peft_type': 'LORA', 'task_type': 'CAUSAL_LM', 'r': int(r), 'lora_alpha': int(r), 'lora_dropout': 0.0, 'bias': 'none',
           'target_modules': targets, 'base_model_name_or_path': base_model, 'fan_in_fan_out': False, 'use_rslora': False,
           'modules_to_save': None}
    json.dump(cfg, open(os.path.join(out_dir, 'adapter_config.json'), 'w'), indent=1)
    if extra:
        json.dump(extra, open(os.path.join(out_dir, 'repair_certificate.json'), 'w'), indent=1)
    return out_dir
