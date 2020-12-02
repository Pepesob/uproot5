# BSD 3-Clause License; see https://github.com/scikit-hep/uproot4/blob/master/LICENSE

"""
Uproot: ROOT I/O in pure Python and NumPy.

Nearly all of the functions needed for general use are imported here, but the
documentation gives fully qualified names. For example, the most frequently
used function in Uproot is

.. code-block:: python

    uproot.open("path/to/filename.root")

but we refer to it in the documentation as :py:func:`~uproot.reading.open`.

Typical entry points for file-reading are

* :py:func:`~uproot.reading.open`
* :py:func:`~uproot.behaviors.TBranch.iterate`
* :py:func:`~uproot.behaviors.TBranch.concatenate`
* :py:func:`~uproot.behaviors.TBranch.lazy`

though they would usually be accessed as ``uproot.iterate``,
``uproot.concatenate``, and ``uproot.lazy``.

The most useful classes are

* :py:class:`~uproot.behaviors.TBranch.HasBranches` (``TTree`` or ``TBranch``)
* :py:class:`~uproot.behaviors.TBranch.TBranch`
* :py:class:`~uproot.behaviors.TH1`
* :py:class:`~uproot.behaviors.TH2`
* :py:class:`~uproot.behaviors.TProfile`

though they would usually be accessed through instances that have been read
from files.

The submodules of Uproot are:

* :py:mod:`uproot.reading`: entry-point for reading files, as well as classes
  for the three basic types that can't be modeled: ``TFile``, ``TDirectory``,
  and ``TKey``.
* :py:mod:`uproot.behaviors`: methods and properties to mix into instantiated
  models, for a high-level user interface.
* :py:mod:`uproot.model`: utilities for modeling C++ objects as Python objects.
* :py:mod:`uproot.streamers`: models for ``TStreamerInfo`` and its elements
  to generate code for new models for classes in ROOT files.
* :py:mod:`uproot.cache`: defines caches with least-recently used eviction
  policies.
* :py:mod:`uproot.compression`: functions for compressing and decompressing data.
* :py:mod:`uproot.deserialization`: utility functions for deserialization,
  including the generation of new classes.
* :py:mod:`uproot.source`: the "physical layer," which reads bytes without
  interpreting them from various backends, like files, HTTP(S), and XRootD.
* :py:mod:`uproot.interpretation`: prescriptions for converting ROOT types
  into Pythonic arrays.
* :py:mod:`uproot.containers`: interpretations and models for standard
  containers, such as ``std::vector`` and arrays.
* :py:mod:`uproot.language`: computational backends for expressions in
  :py:mod:`uproot.behavior.TBranch.HasBranches.arrays`.
* :py:mod:`uproot.models`: predefined models for classes that are too basic
  to rely on ``TStreamerInfo`` or too common to justify reading it.
* :py:mod:`uproot.const`: integer constants used in ROOT serialization and
  deserialization.
* :py:mod:`uproot.extras`: import functions for the libraries that Uproot can
  use, but does not require as dependencies. If a library can't be imported,
  these functions provide instructions for installing them.
* :py:mod:`uproot.version`: for access to the version number.
* :py:mod:`uproot.dynamic`: initially empty module, in which dynamically
  generated classes are defined.
* :py:mod:`uproot._util`: non-public utilities used by the above.
"""

from __future__ import absolute_import

from uproot.version import __version__

import uproot.dynamic

classes = {}
unknown_classes = {}

import uproot.extras

from uproot.cache import LRUCache
from uproot.cache import LRUArrayCache

from uproot.source.file import MemmapSource
from uproot.source.file import MultithreadedFileSource
from uproot.source.http import HTTPSource
from uproot.source.http import MultithreadedHTTPSource
from uproot.source.xrootd import XRootDSource
from uproot.source.xrootd import MultithreadedXRootDSource
from uproot.source.object import ObjectSource
from uproot.source.cursor import Cursor
from uproot.source.futures import TrivialExecutor
from uproot.source.futures import ThreadPoolExecutor
from uproot.deserialization import DeserializationError

from uproot.compression import ZLIB
from uproot.compression import LZMA
from uproot.compression import LZ4
from uproot.compression import ZSTD

from uproot.reading import open
from uproot.reading import ReadOnlyFile
from uproot.reading import ReadOnlyDirectory

from uproot.exceptions import KeyInFileError

from uproot.model import Model
from uproot.model import classname_decode
from uproot.model import classname_encode
from uproot.model import has_class_named
from uproot.model import class_named
from uproot.model import reset_classes

import uproot.models.TObject
import uproot.models.TString
import uproot.models.TArray
import uproot.models.TNamed
import uproot.models.TList
import uproot.models.THashList
import uproot.models.TObjArray
import uproot.models.TObjString
import uproot.models.TAtt
import uproot.models.TRef

import uproot.models.TTree
import uproot.models.TBranch
import uproot.models.TLeaf
import uproot.models.TBasket
import uproot.models.RNTuple

from uproot.containers import STLVector
from uproot.containers import STLSet
from uproot.containers import STLMap

import uproot.interpretation
import uproot.interpretation.identify
import uproot.interpretation.library
from uproot.interpretation.numerical import AsDtype
from uproot.interpretation.numerical import AsDtypeInPlace
from uproot.interpretation.numerical import AsDouble32
from uproot.interpretation.numerical import AsFloat16
from uproot.interpretation.numerical import AsSTLBits
from uproot.interpretation.jagged import AsJagged
from uproot.interpretation.strings import AsStrings
from uproot.interpretation.objects import AsObjects
from uproot.interpretation.objects import AsStridedObjects
from uproot.interpretation.grouped import AsGrouped
from uproot.containers import AsString
from uproot.containers import AsPointer
from uproot.containers import AsArray
from uproot.containers import AsDynamic
from uproot.containers import AsVector
from uproot.containers import AsSet
from uproot.containers import AsMap

default_library = "ak"

from uproot.behaviors.TTree import TTree
from uproot.behaviors.TBranch import TBranch
from uproot.behaviors.TBranch import iterate
from uproot.behaviors.TBranch import concatenate
from uproot.behaviors.TBranch import lazy

import pkgutil
import uproot.behaviors


def behavior_of(classname):
    """
    Finds and loads the behavior class for C++ (decoded) classname or returns
    None if there isn't one.

    Behaviors do not have a required base class, and they may be used with
    Awkward Array's ``ak.behavior``.

    The search strategy for finding behavior classes is:

    1. Translate the ROOT class name from C++ to Python with
       :py:func:`~uproot.model.classname_encode`. For example,
       ``"ROOT::RThing"`` becomes ``"Model_ROOT_3a3a_RThing"``.
    2. Look for a submodule of ``uproot.behaviors`` without
       the ``"Model_"`` prefix. For example, ``"ROOT_3a3a_RThing"``.
    3. Look for a class in that submodule with the fully encoded
       name. For example, ``"Model_ROOT_3a3a_RThing"``.

    See :py:mod:`uproot.behaviors` for details.
    """
    name = classname_encode(classname)
    assert name.startswith("Model_")
    name = name[6:]

    if name not in globals():
        if name in behavior_of._module_names:
            exec(
                compile(
                    "import uproot.behaviors.{0}".format(name), "<dynamic>", "exec"
                ),
                globals(),
            )
            module = eval("uproot.behaviors.{0}".format(name))
            behavior_cls = getattr(module, name, None)
            if behavior_cls is not None:
                globals()[name] = behavior_cls

    return globals().get(name)


behavior_of._module_names = [
    module_name
    for loader, module_name, is_pkg in pkgutil.walk_packages(uproot.behaviors.__path__)
]

del pkgutil

from uproot._util import no_filter