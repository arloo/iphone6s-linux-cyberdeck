CROSS_COMPILE ?= aarch64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
OUTPUT ?= ../../build/cyberdeck-shell-aarch64
.PHONY: all
all: $(OUTPUT)
../fb-cyberdeck/font_data.h:
	$(MAKE) -C ../fb-cyberdeck font_data.h
$(OUTPUT): cyberdeck-shell.c ../fb-cyberdeck/font_data.h
	mkdir -p "$(dir $(OUTPUT))"
	$(CC) -O2 -static -Wall -Wextra -Werror -o "$@" cyberdeck-shell.c -lutil
