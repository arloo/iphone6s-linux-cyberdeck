#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the reset-held N71 SID0 IOMMU/DMA-API diagnostic for the tested batt2 ABI.
Requires the pinned local GPL source after patches0014..0018. No network, USB,
module insertion, endpoint DMA or weakening of the built-in DART guards.
"""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/'experimental/iommu/native-runtime'
def check_sources(source):
 pins=json.loads((TEMPLATE/'source-pins.json').read_text())
 for name,digest in pins.items():
  p=source/'drivers/iommu'/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Pinned GPL source mismatch: '+name)
 return pins
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['kernel-source','kernel-build','patched-source','output']:p.add_argument('--'+name,required=True,type=Path)
 a=p.parse_args();out=a.output.resolve();src=a.patched_source.resolve();pins=check_sources(src)
 if out==ROOT or ROOT in out.parents:raise ValueError('Output must be outside the public source tree')
 release=(a.kernel_build/'include/config/kernel.release').read_text().strip()
 if not release.startswith('7.3.0-rc1-n71-batt2-'):raise ValueError('Use the tested batt2 build/ABI')
 out.mkdir(parents=True,exist_ok=True)
 for f in (ROOT/'experimental/port1').glob('*.h'):shutil.copy2(f,out/f.name)
 for name in ['Makefile','native-runtime.h','native.dts','n71-pgtable-private.c','compat.h']:shutil.copy2(TEMPLATE/name,out/name)
 shutil.copy2(ROOT/'experimental/port1/pcie-apple-s8000-port1-perst-held.c',out/'main.c')
 shutil.copy2(src/'drivers/iommu/apple-dart.c',out/'n71-apple-dart-runtime.c')
 subprocess.run(['git','apply','--unidiff-zero',str(TEMPLATE/'native-driver-adapter.patch')],cwd=out,check=True)
 backend=(src/'drivers/iommu/io-pgtable-dart.c').read_text().replace('io_pgtable_apple_dart_init_fns','n71_pgtable_init_fns')
 (out/'n71-pgtable-backend.c').write_text(backend)
 subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(out/'native.dtbo'),str(out/'native.dts')],check=True,capture_output=True)
 b=(out/'native.dtbo').read_bytes()
 if b'__symbols__' in b or b'__local_fixups__' not in b:raise ValueError('Require local-only phandle fixups for live N71 DT')
 (out/'native-blob.h').write_text('static const unsigned char n71_native_dtbo[] __aligned(8) = {\n'+','.join('0x%02x'%x for x in b)+'\n};\n')
 subprocess.run(['make','-s','-C',str(a.kernel_source.resolve()),'O='+str(a.kernel_build.resolve()),'M='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','modules'],check=True)
 files={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in out.iterdir() if f.suffix in ['.c','.h','.ko','.dtbo']}
 (out/'build-manifest.json').write_text(json.dumps({'kernel_release':release,'source_pins':pins,'files':files,'physically_tested':False,'endpoint_dma_allowed':False},indent=2)+'\n')
 print('N71_NATIVE_IOMMU_RUNTIME_ARM64_BUILD_PASS_NOT_LOADED')
if __name__=='__main__':main()
