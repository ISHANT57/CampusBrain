"""Stub the OCR/extraction stack so API tests can run without it.

`app.api.v1.documents` imports the document-processing chain, which reaches
PaddleOCR -> cv2 -> paddlepaddle plus `unstructured` and PyMuPDF. That is
roughly a gigabyte of vision and ML dependencies, and none of it is touched by
the routing, auth, or serialization these tests exercise.

Installing it to test an auth dependency is the wrong trade. Stubbing the leaf
imports keeps the suite installable and fast, and it is honest about scope:
anything that actually calls extraction is covered by the container build, not
here.

Stubs are registered BEFORE any app import — conftest.py is imported first by
pytest, which is exactly why this lives here rather than in a fixture.
"""

import sys
import types


def _stub(name: str, **attrs) -> None:
    """Register a fake module, but never shadow a real installation."""
    if name in sys.modules:
        return
    try:
        __import__(name)
        return  # genuinely installed; leave it alone
    except ImportError:
        pass

    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


class _Unavailable:
    """Any attribute access returns another _Unavailable; calling raises.

    A silent no-op would let a test appear to exercise extraction while
    exercising nothing. Raising means "this path is not covered here", loudly.
    """

    def __init__(self, *_args, **_kwargs):
        pass

    def __getattr__(self, _name):
        return _Unavailable()

    def __call__(self, *_args, **_kwargs):
        raise RuntimeError(
            "The extraction stack is stubbed in tests. Anything reaching real "
            "OCR or partitioning must be covered by an integration run, not here."
        )


_stub("cv2", imread=_Unavailable(), cvtColor=_Unavailable())
_stub("numpy", array=_Unavailable(), ndarray=_Unavailable)
_stub("fitz", open=_Unavailable(), Document=_Unavailable)
_stub("paddleocr", PaddleOCR=_Unavailable)

_stub("unstructured")
_stub("unstructured.partition")
_stub("unstructured.partition.auto", partition=_Unavailable())
