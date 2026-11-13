# SPDX-License-Identifier: GPL-2.0
# Experimental, default-inert N71 S8000 PMGR module.
# Compile externally against an exactly matching A9 Linux build:
#   make -C <kernel> O=<matching-build> M=<this-dir> ARCH=arm64 modules
# Never activate hardware without a supervised RAM-only test plan.
obj-m += pcie-apple-s8000-port1-powerstage.o
obj-m += pcie-apple-s8000-port1-live-dt-observer.o
