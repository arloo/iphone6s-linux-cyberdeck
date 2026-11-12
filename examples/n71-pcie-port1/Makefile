# Offline nonbootable PCIe/DART safety scaffold.
DTC ?= dtc
PYTHON ?= python3
OUTPUT ?= ../../build/n71-pcie-port1-disabled.dtb
PREFLIGHT_OUTPUT ?= ../../build/n71-pcie-port1-preflight-disabled.dtb

.PHONY: all check replay-check preflight-check clean
all: check
$(OUTPUT): port1-disabled.dts
	mkdir -p "$(dir $(OUTPUT))"
	$(DTC) -q -I dts -O dtb -o "$(OUTPUT)" port1-disabled.dts
check: $(OUTPUT)
	$(PYTHON) ../../tools/n71_pcie_fdt_gate.py "$(OUTPUT)"
# Data-only C replay; no device access, original firmware, or MMIO.
replay-check:
	$(PYTHON) -m unittest discover -s ../../tests -p test_n71_port1_original_tunable_replay_model.py -v
$(PREFLIGHT_OUTPUT): port1-preflight-disabled.dts
	mkdir -p "$(dir $(PREFLIGHT_OUTPUT))"
	$(DTC) -q -I dts -O dtb -o "$(PREFLIGHT_OUTPUT)" port1-preflight-disabled.dts
preflight-check: $(PREFLIGHT_OUTPUT)
	$(PYTHON) ../../tools/n71_s8000_port1_preflight_fdt_gate.py "$(PREFLIGHT_OUTPUT)"
	$(PYTHON) -m unittest discover -s ../../tests -p test_n71_s8000_port1_preflight_fdt_gate.py -v
clean:
	rm -f "$(OUTPUT)" "$(PREFLIGHT_OUTPUT)"
