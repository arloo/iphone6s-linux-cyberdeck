# Experimental Linux fbdev / evdev interactive cyberdeck panel.
# Font raster is generated locally, not distributed in this repository.
CROSS_COMPILE ?= aarch64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
PYTHON ?= python3
LOCAL_TTF ?= /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf
OUTPUT ?= ../../build/cyberdeck-fb-aarch64

.PHONY: all clean
all: $(OUTPUT)
font_data.h: ../../tools/gen_cyberdeck_font.py
	$(PYTHON) $< --font "$(LOCAL_TTF)" --output "$@"
$(OUTPUT): cyberdeck.c font_data.h
	mkdir -p "$(dir $(OUTPUT))"
	$(CC) -O2 -static -Wall -Wextra -Werror -o "$(OUTPUT)" cyberdeck.c
clean:
	rm -f font_data.h
	rm -f "$(OUTPUT)"
