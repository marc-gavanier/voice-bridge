# ADR-004 — CUDA libraries from pip, not from the system

**Date**: 2026-11-10
**Status**: accepted

## Context

Whisper runs on the GPU through faster-whisper and CTranslate2 4.8, which load cuBLAS for CUDA 12 and cuDNN 9 at run time. The workstation runs Ubuntu 24.04 with NVIDIA's driver 595, which supports up to CUDA 13.2, and has no CUDA or cuDNN library installed system-wide; Ubuntu's own repositories carry no usable cuDNN 9.

The project installs both libraries as Python packages, `nvidia-cublas-cu12` and `nvidia-cudnn-cu12`. CTranslate2 does not find them there by itself: without help, transcription fails with *Library libcublas.so.12 is not found or cannot be loaded*.

## Decision

Keep the CUDA libraries as Python packages, locked in `uv.lock` with every other dependency, and run the bridge through `scripts/with-cuda.sh`, which points `LD_LIBRARY_PATH` at them: the method [faster-whisper documents](https://github.com/SYSTRAN/faster-whisper#gpu) for libraries installed with pip.

## Consequences

- `uv sync` alone gives a working GPU setup on any Linux machine with an NVIDIA driver, which matters for a public repository.
- The CUDA libraries are pinned, audited by `uv audit` and updated with the rest of the dependencies.
- Every command that transcribes goes through a six-line wrapper, and the virtual environment carries about a gigabyte of NVIDIA packages.

## Alternatives considered

- **Install CUDA 12 cuBLAS and cuDNN 9 system-wide** from NVIDIA's apt repository, through an Ansible role on the workstation. It removes the wrapper, but adds a third-party package source for one application, leaves the versions of CUDA, cuDNN and CTranslate2 to be matched by hand, and asks every other user of the repository to do the same.
- **Preload the libraries from Python** with `ctypes` before CTranslate2 needs them. It avoids the wrapper by depending on the libraries' load order and on how the dynamic linker matches already loaded libraries, which no tool documents.
