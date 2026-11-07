# Third-party notices

Read Aloud uses the following projects. Their own copyright and licence texts
are included with their distributions where provided.

- [Electron and Chromium](https://www.electronjs.org/docs/latest/tutorial/credits):
  Electron is MIT licensed. Chromium and its dependencies have separate
  licences; Electron's distribution includes `LICENSE` and `LICENSES.chromium.html`.
- [ONNX Runtime](https://github.com/microsoft/onnxruntime): MIT licence.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx): MIT licence.
- [Kokoro-82M v1.0 model and voices](https://huggingface.co/hexgrad/Kokoro-82M):
  Apache License 2.0. The model card credits the CC BY 3.0 Koniwa and CC BY 4.0
  SIWIS audio used in training. The ONNX export and voices are downloaded on
  first run from [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).
- [Python](https://docs.python.org/3/license.html): Python Software Foundation
  License; the runtime comes from [python-build-standalone](https://github.com/astral-sh/python-build-standalone).
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng): GPL 3.0 or later;
  supplied by [espeakng-loader](https://github.com/thewh1teagle/espeakng-loader).
- [SoundFile](https://github.com/bastibe/python-soundfile) and its bundled
  libsndfile, and the Python and JavaScript dependencies, have their own licence
  notices in their installed distributions.

Before distributing artifacts, audit the exact built dependency versions,
licence texts and corresponding source, including the eSpeak NG binary and
any changes used to build it. This file is an index, not that completed audit.
