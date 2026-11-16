CROSS_COMPILE ?= aarch64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
PYTHON ?= python3
LOCAL_TTF ?= /usr/share/fonts/truetype/ibm-plex/IBMPlexMono-Medium.ttf
OUTPUT ?= ../../build/cyberdeck-shell-aarch64
.PHONY: all
all: $(OUTPUT)
font_aa.h: ../../tools/gen_cyberdeck_aa_font.py $(LOCAL_TTF)
	$(PYTHON) ../../tools/gen_cyberdeck_aa_font.py --font "$(LOCAL_TTF)" --output "$@"
$(OUTPUT): cyberdeck-shell.c font_aa.h
	mkdir -p "$(dir $(OUTPUT))"
	$(CC) -O2 -static -Wall -Wextra -Werror -o "$@" cyberdeck-shell.c -lutil
