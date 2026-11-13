# SPDX-License-Identifier: GPL-2.0
# Experimental, default-inert N71 S8000 PMGR module.
# Compile externally against an exactly matching A9 Linux build:
#   make -C <kernel> O=<matching-build> M=<this-dir> ARCH=arm64 modules
# Never activate hardware without a supervised RAM-only test plan.
obj-m += pcie-apple-s8000-port1-powerstage.o
obj-m += pcie-apple-s8000-port1-live-dt-observer.o
obj-m += pcie-apple-s8000-port1-runtime-sandbox.o
obj-m += pcie-apple-s8000-port1-powerstage-overlay-inert.o
obj-m += pcie-apple-s8000-port1-refclk-microlease.o
obj-m += pcie-apple-s8000-port1-aux-microlease.o
obj-m += pcie-apple-s8000-port1-root-microlease.o
obj-m += pcie-apple-s8000-port1-link1-microlease.o
obj-m += pcie-apple-s8000-port1-triplet-microlease.o
obj-m += pcie-apple-s8000-port1-status-snapshot.o
obj-m += pcie-apple-s8000-port1-id3-id2-stage.o
