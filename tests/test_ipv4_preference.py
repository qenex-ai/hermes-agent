"""Tests for network.force_ipv4 — the socket.getaddrinfo monkey-patch."""

import errno
import importlib
import socket



def _reload_constants():
    """Reload hermes_constants to get a fresh apply_ipv4_preference."""
    import hermes_constants
    importlib.reload(hermes_constants)
    return hermes_constants


class TestApplyIPv4Preference:
    """Tests for apply_ipv4_preference()."""

    def setup_method(self):
        """Save the original getaddrinfo before each test."""
        import hermes_constants as hc

        self._original = socket.getaddrinfo
        self._saved_ipv6_cache = hc._IPV6_SOCKETS_SUPPORTED
        hc._IPV6_SOCKETS_SUPPORTED = None

    def teardown_method(self):
        """Restore the original getaddrinfo after each test."""
        import hermes_constants as hc

        socket.getaddrinfo = self._original
        hc._IPV6_SOCKETS_SUPPORTED = self._saved_ipv6_cache


    def test_patches_getaddrinfo_when_forced(self):
        """Patches socket.getaddrinfo when force=True."""
        from hermes_constants import apply_ipv4_preference
        original = socket.getaddrinfo
        apply_ipv4_preference(force=True)
        assert socket.getaddrinfo is not original
        assert getattr(socket.getaddrinfo, "_hermes_ipv4_patched", False) is True

    def test_double_patch_is_safe(self):
        """Calling apply twice doesn't double-wrap."""
        from hermes_constants import apply_ipv4_preference
        apply_ipv4_preference(force=True)
        first_patch = socket.getaddrinfo
        apply_ipv4_preference(force=True)
        assert socket.getaddrinfo is first_patch

    def test_af_unspec_becomes_af_inet(self):
        """AF_UNSPEC (default) calls get rewritten to AF_INET."""
        from hermes_constants import apply_ipv4_preference

        calls = []
        original = socket.getaddrinfo

        def mock_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            calls.append(family)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

        socket.getaddrinfo = mock_getaddrinfo
        apply_ipv4_preference(force=True)

        # Call with default family (AF_UNSPEC = 0)
        socket.getaddrinfo("example.com", 80)
        assert calls[-1] == socket.AF_INET, "AF_UNSPEC should be rewritten to AF_INET"

    def test_explicit_family_preserved(self):
        """Explicit AF_INET6 requests are not intercepted."""
        from hermes_constants import apply_ipv4_preference

        calls = []
        original = socket.getaddrinfo

        def mock_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            calls.append(family)
            return [(family, socket.SOCK_STREAM, 6, "", ("::1", 80))]

        socket.getaddrinfo = mock_getaddrinfo
        apply_ipv4_preference(force=True)

        socket.getaddrinfo("example.com", 80, family=socket.AF_INET6)
        assert calls[-1] == socket.AF_INET6, "Explicit AF_INET6 should pass through"

    def test_probe_false_on_eafnosupport(self, monkeypatch):
        """Kernel EAFNOSUPPORT is a hard no — not socket.has_ipv6."""
        import hermes_constants as hc

        real_socket = socket.socket

        def _socket(family=-1, *args, **kwargs):
            if family == socket.AF_INET6:
                raise OSError(errno.EAFNOSUPPORT, "Address family not supported by protocol")
            return real_socket(family, *args, **kwargs)

        monkeypatch.setattr(socket, "socket", _socket)
        assert hc.ipv6_sockets_supported() is False

    def test_apply_without_force_patches_when_ipv6_unavailable(self):
        """Dashboard OAuth on IPv6-disabled hosts must patch without config."""
        import hermes_constants as hc

        hc._IPV6_SOCKETS_SUPPORTED = False
        original = socket.getaddrinfo
        hc.apply_ipv4_preference(force=False)
        assert socket.getaddrinfo is not original
        assert getattr(socket.getaddrinfo, "_hermes_ipv4_patched", False) is True

    def test_apply_without_force_skips_when_ipv6_available(self):
        """Dual-stack hosts keep AAAA unless network.force_ipv4 is set."""
        import hermes_constants as hc

        hc._IPV6_SOCKETS_SUPPORTED = True
        original = socket.getaddrinfo
        hc.apply_ipv4_preference(force=False)
        assert socket.getaddrinfo is original

    def test_is_address_family_unsupported_unwraps_cause(self):
        """httpx wraps errno 97; the detector must see the OSError cause."""
        from hermes_constants import is_address_family_unsupported

        inner = OSError(errno.EAFNOSUPPORT, "Address family not supported by protocol")
        outer = ConnectionError("All connection attempts failed")
        outer.__cause__ = inner
        assert is_address_family_unsupported(outer) is True
        assert is_address_family_unsupported(RuntimeError("timeout")) is False
