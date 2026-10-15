"""Prepare individual product screens and internal design-QA comparisons."""
from pathlib import Path
from PIL import Image, ImageOps
import shutil

root=Path(__file__).resolve().parents[1]
out=root/'public'/'screens'
out.mkdir(parents=True,exist_ok=True)
for path in (root/'evidence').glob('*.jpg'):
    with Image.open(path) as img:
        if img.size != (1440,1024):
            raise SystemExit(f'Wrong screenshot dimensions: {path.name} {img.size}')
    shutil.copy2(path,out/path.name)
source=Path('C:/Users/admin-2/.codex/generated_images/01a1316a-08a9-74c2-a724-7a4d06c158ef/exec-974f0d07-99aa-4d25-a5b8-075f6327a163.png')
source_img=Image.open(source).convert('RGB')
reference=Image.new('RGB',(1440,1024),'white')
normalized=ImageOps.contain(source_img,(1440,1024),Image.Resampling.LANCZOS)
reference.paste(normalized,((1440-normalized.width)//2,(1024-normalized.height)//2))
impl=Image.open(root/'evidence'/'03-visual-builder.jpg').convert('RGB')
pair=Image.new('RGB',(2880,1024),'white');pair.paste(reference,(0,0));pair.paste(impl,(1440,0));pair.save(root/'evidence'/'qa-full-comparison.png')
source_crop=reference.crop((615,275,1008,890))
impl_crop=impl.crop((680,325,1045,1008))
crop_pair=Image.new('RGB',(900,800),'white')
for i,crop in enumerate((source_crop,impl_crop)):
    fitted=ImageOps.contain(crop,(450,800),Image.Resampling.LANCZOS)
    crop_pair.paste(fitted,(i*450,0))
crop_pair.save(root/'evidence'/'qa-inspector-comparison.png')
print(f'Prepared {len(list(out.glob("*.jpg")))} separate screens. Source pixels: {source_img.size}.')
