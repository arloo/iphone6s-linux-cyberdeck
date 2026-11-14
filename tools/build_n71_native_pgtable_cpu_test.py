#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the CPU-only DART table test from a local patched GPL kernel source.
No downloads, phone access, module loading, MMIO or DMA.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
def backend(source):
 text=source.read_text()
 required=['APPLE_DART_S5L8960X_TABLE_VALID','IO_PGTABLE_QUIRK_APPLE_DART_S5L8960X','new |= APPLE_DART_S5L8960X_TABLE_VALID;']
 if not all(s in text for s in required):raise ValueError('Apply attributed patch0018 before building')
 if text.count('struct io_pgtable_init_fns io_pgtable_apple_dart_init_fns')!=1:raise ValueError('Unexpected source allocator')
 return text.replace('io_pgtable_apple_dart_init_fns','n71_pgtable_init_fns')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['kernel-source','kernel-build','patched-source','output']:p.add_argument('--'+name,required=True,type=Path)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 if out==ROOT or ROOT in out.parents:raise ValueError('Use an output directory outside the public source tree')
 source=a.patched_source.resolve()/'drivers/iommu/io-pgtable-dart.c'
 text=backend(source)
 for name in ['main.c','compat.h','Makefile']:shutil.copy2(ROOT/'experimental/iommu/native-pgtable-test'/name,out/name)
 (out/'n71-pgtable-backend.c').write_text(text)
 subprocess.run(['make','-s','-C',str(a.kernel_source.resolve()),'O='+str(a.kernel_build.resolve()),'M='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','modules'],check=True)
 files={}
 for f in out.iterdir():
  if f.suffix in ['.c','.h','.ko']:files[f.name]={'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 (out/'build-manifest.json').write_text(json.dumps({'cpu_only':True,'physically_executed':False,'files':files},indent=2)+'\n')
 print('N71_PGTABLE_CPU_TEST_ARM64_BUILD_PASS_NOT_LOADED')
if __name__=='__main__':main()
