from __future__ import absolute_import

import re
import warnings

from pip._internal.utils.typing import MYPY_CHECK_RUNNING

# Work around https://bugs.python.org/issue37060.
try:
    import ctypes
except (ImportError, OSError):
    ctypes = None

if MYPY_CHECK_RUNNING:
    from typing import Optional, Tuple


def glibc_version_string():
    # type: () -> Optional[str]
    "Returns glibc version string, or None if not using glibc."

    if not ctypes:
        return None

    # ctypes.CDLL(None) internally calls dlopen(NULL), and as the dlopen
    # manpage says, "If filename is NULL, then the returned handle is for the
    # main program". This way we can let the linker do the work to figure out
    # which libc our process is actually using.
    process_namespace = ctypes.CDLL(None)
    try:
        gnu_get_libc_version = process_namespace.gnu_get_libc_version
    except AttributeError:
        # Symbol doesn't exist -> therefore, we are not linked to
        # glibc.
        return None

    # Call gnu_get_libc_version, which returns a string like "2.5"
    gnu_get_libc_version.restype = ctypes.c_char_p
    version_str = gnu_get_libc_version()
    # py2 / py3 compatibility:
    if not isinstance(version_str, str):
        version_str = version_str.decode("ascii")

    return version_str


# Separated out from have_compatible_glibc for easier unit testing
def check_glibc_version(version_str, required_major, minimum_minor):
    # type: (str, int, int) -> bool
    # Parse string and check against requested version.
    #
    # We use a regexp instead of str.split because we want to discard any
    # random junk that might come after the minor version -- this might happen
    # in patched/forked versions of glibc (e.g. Linaro's version of glibc
    # uses version strings like "2.20-2014.11"). See gh-3588.
    m = re.match(r"(?P<major>[0-9]+)\.(?P<minor>[0-9]+)", version_str)
    if not m:
        warnings.warn("Expected glibc version with 2 components major.minor,"
                      " got: %s" % version_str, RuntimeWarning)
        return False
    return (int(m.group("major")) == required_major and
            int(m.group("minor")) >= minimum_minor)


def have_compatible_glibc(required_major, minimum_minor):
    # type: (int, int) -> bool
    version_str = glibc_version_string()  # type: Optional[str]
    if version_str is None:
        return False
    return check_glibc_version(version_str, required_major, minimum_minor)


# platform.libc_ver regularly returns completely nonsensical glibc
# versions. E.g. on my computer, platform says:
#
#   ~$ python2.7 -c 'import platform; print(platform.libc_ver())'
#   ('glibc', '2.7')
#   ~$ python3.5 -c 'import platform; print(platform.libc_ver())'
#   ('glibc', '2.9')
#
# But the truth is:
#
#   ~$ ldd --version
#   ldd (Debian GLIBC 2.22-11) 2.22
#
# This is unfortunate, because it means that the linehaul data on libc
# versions that was generated by pip 8.1.2 and earlier is useless and
# misleading. Solution: instead of using platform, use our code that actually
# works.
def libc_ver():
    # type: () -> Tuple[str, str]
    """Try to determine the glibc version

    Returns a tuple of strings (lib, version) which default to empty strings
    in case the lookup fails.
    """
    glibc_version = glibc_version_string()
    if glibc_version is None:
        return ("", "")
    else:
        return ("glibc", glibc_version)
