# Makefile — QNX 8.0 recursive makefile for the hello project.
# Build on the host with the QNX SDP 8.0 toolchain (qcc/make):
#   make            # builds for $(TARGET_CPU)
#   make install    # installs into $(INSTALLDIR)
TARGET_CPU = aarch64le
USEFILE = $(PROJECT_ROOT)/usage.txt
INSTALLDIR = usr/bin
EXTRA_CCOPTS += -Wall -Wextra

include $(QNX_TARGET)/usr/include/mk/common.mk
