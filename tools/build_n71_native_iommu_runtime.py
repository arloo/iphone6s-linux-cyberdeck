#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the default reset-held N71 diagnostic or explicit managed WLAN runtime.
Requires the pinned GPL source after patches0014..0018 and owner calibration
for native WLAN modes. Builds only: no device access or module insertion.
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
 p.add_argument("--private-calibration",type=Path)
 p.add_argument("--native-msi-domain",action="store_true")
 p.add_argument("--brcmfmac-trial",action="store_true")
 p.add_argument("--managed-wlan-runtime",action="store_true")
 p.add_argument("--live-seconds",type=int,default=0)
 a=p.parse_args()
 if a.managed_wlan_runtime:a.brcmfmac_trial=True
 if a.brcmfmac_trial:a.native_msi_domain=True
 if not 0<=a.live_seconds<=120:raise ValueError('Live trial must remain within0..120seconds')
 if (a.brcmfmac_trial or a.native_msi_domain) and not a.private_calibration:raise ValueError('Native runtime requires the owner calibration')
 if a.live_seconds and (not a.brcmfmac_trial or a.managed_wlan_runtime):raise ValueError('Use live-seconds only for the bounded brcmfmac trial')
 out=a.output.resolve();src=a.patched_source.resolve();pins=check_sources(src)
 if out==ROOT or ROOT in out.parents:raise ValueError('Output must be outside the public source tree')
 release=(a.kernel_build/'include/config/kernel.release').read_text().strip()
 if not release.startswith('7.3.0-rc1-n71-batt2-'):raise ValueError('Use the tested batt2 build/ABI')
 out.mkdir(parents=True,exist_ok=True)
 for f in (ROOT/'experimental/port1').glob('*.h'):shutil.copy2(f,out/f.name)
 for name in ['Makefile','native-runtime.h','n71-protocol6-rings.h','n71-protocol6-msi.h','n71-native-msi-domain.h','n71-brcmfmac-bind-trial.h','native.dts','n71-pgtable-private.c','compat.h']:shutil.copy2(TEMPLATE/name,out/name)
 shutil.copy2(ROOT/'experimental/port1/pcie-apple-s8000-port1-perst-held.c',out/'main.c')
 shutil.copy2(src/'drivers/iommu/apple-dart.c',out/'n71-apple-dart-runtime.c')
 subprocess.run(['git','apply','--unidiff-zero',str(TEMPLATE/'native-driver-adapter.patch')],cwd=out,check=True)
 backend=(src/'drivers/iommu/io-pgtable-dart.c').read_text().replace('io_pgtable_apple_dart_init_fns','n71_pgtable_init_fns')
 (out/'n71-pgtable-backend.c').write_text(backend)
 if a.private_calibration:
  data=a.private_calibration.read_bytes()
  if b'n71_private_calibration' not in data:raise ValueError('Invalid owner calibration header')
  (out/'n71-private-port1-calibration.h').write_bytes(data)
  with (out/'Makefile').open('a') as f:f.write('\nccflags-y += -DN71_PRIVATE_PORT1_CALIBRATION\n')
 flags=[]
 if a.native_msi_domain:flags.append('-DN71_NATIVE_MSI_DOMAIN')
 if a.brcmfmac_trial:flags.append('-DN71_NATIVE_BRCMFMAC_TRIAL')
 if a.managed_wlan_runtime:flags.append('-DN71_NATIVE_WLAN_RUNTIME')
 if a.live_seconds:flags.append('-DN71_BRCMFMAC_LIVE_SECONDS='+str(a.live_seconds))
 if flags:
  with (out/'Makefile').open('a') as f:f.write('\nccflags-y += '+' '.join(flags)+'\n')
 subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(out/'native.dtbo'),str(out/'native.dts')],check=True,capture_output=True)
 b=(out/'native.dtbo').read_bytes()
 if b'__symbols__' in b or b'__local_fixups__' not in b:raise ValueError('Require local-only phandle fixups for live N71 DT')
 (out/'native-blob.h').write_text('static const unsigned char n71_native_dtbo[] __aligned(8) = {\n'+','.join('0x%02x'%x for x in b)+'\n};\n')
 subprocess.run(['make','-s','-C',str(a.kernel_source.resolve()),'O='+str(a.kernel_build.resolve()),'M='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','modules'],check=True)
 files={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in out.iterdir() if f.suffix in ['.c','.h','.ko','.dtbo']}
 (out/'build-manifest.json').write_text(json.dumps({'kernel_release':release,'source_pins':pins,'files':files,'physically_tested':False,'endpoint_dma_allowed':a.brcmfmac_trial,'native_msi_domain':a.native_msi_domain,'managed_wlan_runtime':a.managed_wlan_runtime,'live_seconds':a.live_seconds},indent=2)+'\n')
 print('N71_NATIVE_IOMMU_RUNTIME_ARM64_BUILD_PASS_NOT_LOADED')
if __name__=='__main__':main()
