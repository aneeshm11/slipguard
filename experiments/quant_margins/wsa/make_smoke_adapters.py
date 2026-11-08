import os  # added by the repo export (paths are env/config driven)
import sys, torch
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa'))
from lora_io import write_peft_adapter
g = torch.Generator().manual_seed(0)
r = 8
A = torch.randn(r, 21504, generator=g) * 0.02; B = torch.randn(5376, r, generator=g) * 0.5
for variant, scale in (('zero', 0.0), ('rand', 1.0)):
    write_peft_adapter(fos.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/quant_margins/wsa/adapters/smoke_{variant}'),
                       {'model.layers.59.mlp.down_proj': (A, B * scale)})
print('ok')
